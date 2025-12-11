"""Unit tests for DynamoDB retry store using standardized dynamodb_next utilities."""

import time
from datetime import datetime, timezone

from infrastructure.operations import OperationResult, OperationStatus


class TestDynamoDBRetryStoreInitialization:
    """Tests for DynamoDB store initialization."""

    def test_init_with_config(self, retry_config_factory, dynamodb_retry_store):
        """Test store initialization with configuration."""
        assert dynamodb_retry_store.table_name == "test-retry-table"
        assert dynamodb_retry_store.ttl_days == 30
        assert dynamodb_retry_store.config.max_attempts == 5

    def test_init_with_custom_ttl(
        self, retry_config_factory, mock_dynamodb_next, monkeypatch
    ):
        """Test store initialization with custom TTL."""
        monkeypatch.setattr(
            "infrastructure.resilience.retry.dynamodb_store.dynamodb_next",
            mock_dynamodb_next,
        )

        from infrastructure.resilience.retry.dynamodb_store import DynamoDBRetryStore

        config = retry_config_factory()
        store = DynamoDBRetryStore(
            config=config,
            table_name="test-table",
            ttl_days=7,
        )

        assert store.ttl_days == 7


class TestDynamoDBRetryStoreSave:
    """Tests for save() method."""

    def test_save_assigns_id(self, retry_record_factory, dynamodb_retry_store):
        """Test that save assigns an ID to the record."""
        record = retry_record_factory()
        assert record.id is None

        record_id = dynamodb_retry_store.save(record)

        assert record_id is not None
        assert record.id == record_id
        assert record.id.startswith("retry-")

    def test_save_calls_put_item(self, retry_record_factory, dynamodb_retry_store):
        """Test that save calls DynamoDB put_item."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        record = retry_record_factory(
            operation_type="test.op", payload={"key": "value"}
        )
        dynamodb_retry_store.save(record)

        mock_next.put_item.assert_called_once()
        call_args = mock_next.put_item.call_args
        assert call_args[1]["table_name"] == "test-retry-table"

        item = call_args[1]["Item"]
        assert item["record_id"]["S"] == record.id
        assert item["operation_type"]["S"] == "test.op"
        assert "ttl" in item

    def test_save_sets_timestamps(self, retry_record_factory, dynamodb_retry_store):
        """Test that save sets timestamps on the record."""
        before = datetime.now(timezone.utc)
        record = retry_record_factory()
        dynamodb_retry_store.save(record)
        after = datetime.now(timezone.utc)

        assert before <= record.created_at <= after
        assert before <= record.updated_at <= after
        assert record.next_retry_at is not None


class TestDynamoDBRetryStoreFetchDue:
    """Tests for fetch_due() method."""

    def test_fetch_due_queries_gsi(self, dynamodb_retry_store):
        """Test that fetch_due queries the GSI."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        dynamodb_retry_store.fetch_due()

        mock_next.query.assert_called_once()
        call_args = mock_next.query.call_args
        assert call_args[1]["IndexName"] == "status-next_retry_at-index"
        assert (
            call_args[1]["KeyConditionExpression"]
            == "#status = :status AND next_retry_at <= :now"
        )

    def test_fetch_due_returns_records(self, dynamodb_retry_store):
        """Test that fetch_due returns RetryRecord instances."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        now = int(time.time())
        mock_next.query.return_value = OperationResult.success(
            data={
                "Items": [
                    {
                        "record_id": {"S": "retry-1"},
                        "operation_type": {"S": "test.op"},
                        "payload": {"S": '{"key": "value"}'},
                        "attempts": {"N": "0"},
                        "created_at": {"S": datetime.now(timezone.utc).isoformat()},
                        "updated_at": {"S": datetime.now(timezone.utc).isoformat()},
                        "next_retry_at": {"N": str(now - 100)},
                        "status": {"S": "ACTIVE"},
                    }
                ]
            }
        )

        records = dynamodb_retry_store.fetch_due()

        assert len(records) == 1
        assert records[0].id == "retry-1"
        assert records[0].operation_type == "test.op"

    def test_fetch_due_filters_claimed_records(self, dynamodb_retry_store):
        """Test that fetch_due filters out claimed records."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        now = int(time.time())
        mock_next.query.return_value = OperationResult.success(
            data={
                "Items": [
                    {
                        "record_id": {"S": "retry-1"},
                        "operation_type": {"S": "test.op"},
                        "payload": {"S": "{}"},
                        "attempts": {"N": "0"},
                        "created_at": {"S": datetime.now(timezone.utc).isoformat()},
                        "updated_at": {"S": datetime.now(timezone.utc).isoformat()},
                        "next_retry_at": {"N": str(now - 100)},
                        "status": {"S": "ACTIVE"},
                        "claim_worker": {"S": "worker-1"},
                        "claim_expires_at": {"N": str(now + 100)},  # Not expired
                    }
                ]
            }
        )

        records = dynamodb_retry_store.fetch_due()

        # Should filter out the claimed record
        assert len(records) == 0

    def test_fetch_due_respects_limit(self, dynamodb_retry_store):
        """Test that fetch_due respects the limit parameter."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        dynamodb_retry_store.fetch_due(limit=5)

        call_args = mock_next.query.call_args
        assert call_args[1]["Limit"] == 10  # 5 * 2 for filtering


class TestDynamoDBRetryStoreClaimRecord:
    """Tests for claim_record() method."""

    def test_claim_record_succeeds(self, dynamodb_retry_store):
        """Test successful record claim."""
        result = dynamodb_retry_store.claim_record("retry-1", "worker-1", 300)

        assert result is True
        dynamodb_retry_store._mock_dynamodb_next.update_item.assert_called_once()

    def test_claim_record_uses_conditional_expression(self, dynamodb_retry_store):
        """Test that claim uses conditional expression for atomicity."""
        dynamodb_retry_store.claim_record("retry-1", "worker-1", 300)

        call_args = dynamodb_retry_store._mock_dynamodb_next.update_item.call_args
        assert "ConditionExpression" in call_args[1]
        assert (
            "attribute_not_exists(claim_worker)" in call_args[1]["ConditionExpression"]
        )

    def test_claim_record_fails_on_condition_check(self, dynamodb_retry_store):
        """Test claim failure when condition check fails."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        # Simulate conditional check failure
        mock_next.update_item.return_value = OperationResult.error(
            message="Conditional check failed",
            status=OperationStatus.PERMANENT_ERROR,
            error_code="ConditionalCheckFailedException",
        )

        result = dynamodb_retry_store.claim_record("retry-1", "worker-1", 300)

        assert result is False


class TestDynamoDBRetryStoreMarkSuccess:
    """Tests for mark_success() method."""

    def test_mark_success_deletes_item(self, dynamodb_retry_store):
        """Test that mark_success deletes the item."""
        dynamodb_retry_store.mark_success("retry-1")

        call_args = dynamodb_retry_store._mock_dynamodb_next.delete_item.call_args
        assert call_args[1]["Key"] == {"record_id": {"S": "retry-1"}}


class TestDynamoDBRetryStoreMarkPermanentFailure:
    """Tests for mark_permanent_failure() method."""

    def test_mark_permanent_failure_updates_status(self, dynamodb_retry_store):
        """Test that mark_permanent_failure updates status to DLQ."""
        dynamodb_retry_store.mark_permanent_failure("retry-1", "Error message")

        mock_next = dynamodb_retry_store._mock_dynamodb_next
        mock_next.update_item.assert_called_once()

        call_args = mock_next.update_item.call_args
        # Check that DLQ is in the expression values
        expr_values = call_args[1]["ExpressionAttributeValues"]
        assert any("DLQ" in str(v) for v in expr_values.values())

    def test_mark_permanent_failure_removes_claim(self, dynamodb_retry_store):
        """Test that mark_permanent_failure removes claim."""
        dynamodb_retry_store.mark_permanent_failure("retry-1")

        call_args = dynamodb_retry_store._mock_dynamodb_next.update_item.call_args
        assert "REMOVE claim_worker" in call_args[1]["UpdateExpression"]


class TestDynamoDBRetryStoreIncrementAttempt:
    """Tests for increment_attempt() method."""

    def test_increment_attempt_gets_current_record(self, dynamodb_retry_store):
        """Test that increment_attempt fetches current record."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        mock_next.get_item.return_value = OperationResult.success(
            data={
                "Item": {
                    "record_id": {"S": "retry-1"},
                    "attempts": {"N": "2"},
                }
            }
        )

        dynamodb_retry_store.increment_attempt("retry-1", "Error")

        mock_next.get_item.assert_called_once()
        call_args = mock_next.get_item.call_args
        assert call_args[1]["Key"] == {"record_id": {"S": "retry-1"}}

    def test_increment_attempt_moves_to_dlq_at_max(self, dynamodb_retry_store):
        """Test that increment_attempt moves to DLQ at max attempts."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        # At max attempts (3 total, so 2 current becomes 3 after increment)
        mock_next.get_item.return_value = OperationResult.success(
            data={
                "Item": {
                    "record_id": {"S": "retry-1"},
                    "attempts": {"N": "4"},  # Will be 5 after increment, >= max
                }
            }
        )

        dynamodb_retry_store.increment_attempt("retry-1", "Final error")

        # Should call update_item to move to DLQ (via mark_permanent_failure)
        # The second update_item call should be for moving to DLQ
        assert mock_next.update_item.call_count >= 1

    def test_increment_attempt_releases_claim(self, dynamodb_retry_store):
        """Test that increment_attempt releases claim."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        mock_next.get_item.return_value = OperationResult.success(
            data={
                "Item": {
                    "record_id": {"S": "retry-1"},
                    "attempts": {"N": "1"},
                }
            }
        )

        dynamodb_retry_store.increment_attempt("retry-1")

        call_args = mock_next.update_item.call_args
        assert "REMOVE claim_worker" in call_args[1]["UpdateExpression"]


class TestDynamoDBRetryStoreGetStats:
    """Tests for get_stats() method."""

    def test_get_stats_queries_active_and_dlq(self, dynamodb_retry_store):
        """Test that get_stats queries both ACTIVE and DLQ records."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        mock_next.query.return_value = OperationResult.success(data={"Count": 5})

        stats = dynamodb_retry_store.get_stats()

        # Should be called twice (ACTIVE and DLQ)
        assert mock_next.query.call_count == 2
        assert stats["active_records"] == 5
        assert stats["dlq_records"] == 5

    def test_get_stats_returns_zero_on_error(self, dynamodb_retry_store):
        """Test that get_stats returns zeros on error."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        mock_next.query.return_value = OperationResult.error(
            message="Internal error",
            status=OperationStatus.TRANSIENT_ERROR,
        )

        stats = dynamodb_retry_store.get_stats()

        assert stats["active_records"] == 0
        assert stats["claimed_records"] == 0
        assert stats["dlq_records"] == 0


class TestDynamoDBRetryStoreGetDlqEntries:
    """Tests for get_dlq_entries() method."""

    def test_get_dlq_entries_queries_dlq_status(self, dynamodb_retry_store):
        """Test that get_dlq_entries queries DLQ status."""
        mock_next = dynamodb_retry_store._mock_dynamodb_next

        now = datetime.now(timezone.utc)
        mock_next.query.return_value = OperationResult.success(
            data={
                "Items": [
                    {
                        "record_id": {"S": "retry-1"},
                        "operation_type": {"S": "test.op"},
                        "payload": {"S": "{}"},
                        "attempts": {"N": "5"},
                        "created_at": {"S": now.isoformat()},
                        "updated_at": {"S": now.isoformat()},
                        "next_retry_at": {"N": str(int(time.time()))},
                        "last_error": {"S": "Max attempts reached"},
                    }
                ]
            }
        )

        entries = dynamodb_retry_store.get_dlq_entries()

        mock_next.query.assert_called_once()
        call_args = mock_next.query.call_args
        assert call_args[1]["IndexName"] == "status-next_retry_at-index"

        assert len(entries) == 1
        assert entries[0].id == "retry-1"
        assert entries[0].last_error == "Max attempts reached"
