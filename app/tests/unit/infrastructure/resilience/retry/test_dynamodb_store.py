"""Unit tests for DynamoDB retry store behavior with boto3-shaped responses."""

import time
from datetime import UTC, datetime

import pytest
from botocore.exceptions import ClientError
from structlog.testing import capture_logs

from infrastructure.resilience.retry.dynamodb_store import DynamoDBRetryStore


def _client_error(error_code: str, operation_name: str) -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": error_code, "Message": "DynamoDB request failed"}},
        operation_name=operation_name,
    )


class TestDynamoDBRetryStoreInitialization:
    """Tests for DynamoDB store initialization."""

    def test_init_with_config(self, retry_config_factory, dynamodb_retry_store):
        """Test store initialization with configuration."""
        assert dynamodb_retry_store.table_name == "test-retry-table"
        assert dynamodb_retry_store.ttl_days == 30
        assert dynamodb_retry_store.config.max_attempts == 5

    def test_init_with_custom_ttl(self, retry_config_factory, mock_dynamodb_client):
        """Test store initialization with custom TTL."""
        config = retry_config_factory()
        store = DynamoDBRetryStore(
            mock_dynamodb_client,
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
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb

        record = retry_record_factory(operation_type="test.op", payload={"key": "value"})
        dynamodb_retry_store.save(record)

        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]["TableName"] == "test-retry-table"

        item = call_args[1]["Item"]
        assert item["record_id"]["S"] == record.id
        assert item["operation_type"]["S"] == "test.op"
        assert "ttl" in item

    def test_save_raises_runtime_error_on_classified_failure(self, retry_record_factory, dynamodb_retry_store):
        """A classified write failure is logged and surfaced as a runtime error."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb
        mock_dynamodb.put_item.side_effect = _client_error("AccessDeniedException", "PutItem")

        with pytest.raises(RuntimeError, match="Failed to save retry record"):
            dynamodb_retry_store.save(retry_record_factory())

    def test_save_sets_timestamps(self, retry_record_factory, dynamodb_retry_store):
        """Test that save sets timestamps on the record."""
        before = datetime.now(UTC)
        record = retry_record_factory()
        dynamodb_retry_store.save(record)
        after = datetime.now(UTC)

        assert before <= record.created_at <= after
        assert before <= record.updated_at <= after
        assert record.next_retry_at is not None


class TestDynamoDBRetryStoreFetchDue:
    """Tests for fetch_due() method."""

    def test_fetch_due_queries_gsi(self, dynamodb_retry_store):
        """Test that fetch_due queries the GSI."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb

        dynamodb_retry_store.fetch_due()

        mock_dynamodb.query.assert_called_once()
        call_args = mock_dynamodb.query.call_args
        assert call_args[1]["TableName"] == "test-retry-table"
        assert call_args[1]["IndexName"] == "status-next_retry_at-index"
        assert call_args[1]["KeyConditionExpression"] == "#status = :status AND next_retry_at <= :now"

    def test_fetch_due_returns_records(self, dynamodb_retry_store):
        """Test that fetch_due returns RetryRecord instances."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb

        now = int(time.time())
        mock_dynamodb.query.return_value = {
            "Items": [
                {
                    "record_id": {"S": "retry-1"},
                    "operation_type": {"S": "test.op"},
                    "payload": {"S": '{"key": "value"}'},
                    "attempts": {"N": "0"},
                    "created_at": {"S": datetime.now(UTC).isoformat()},
                    "updated_at": {"S": datetime.now(UTC).isoformat()},
                    "next_retry_at": {"N": str(now - 100)},
                    "status": {"S": "ACTIVE"},
                }
            ]
        }

        records = dynamodb_retry_store.fetch_due()

        assert len(records) == 1
        assert records[0].id == "retry-1"
        assert records[0].operation_type == "test.op"

    def test_fetch_due_filters_claimed_records(self, dynamodb_retry_store):
        """Test that fetch_due filters out claimed records."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb

        now = int(time.time())
        mock_dynamodb.query.return_value = {
            "Items": [
                {
                    "record_id": {"S": "retry-1"},
                    "operation_type": {"S": "test.op"},
                    "payload": {"S": "{}"},
                    "attempts": {"N": "0"},
                    "created_at": {"S": datetime.now(UTC).isoformat()},
                    "updated_at": {"S": datetime.now(UTC).isoformat()},
                    "next_retry_at": {"N": str(now - 100)},
                    "status": {"S": "ACTIVE"},
                    "claim_worker": {"S": "worker-1"},
                    "claim_expires_at": {"N": str(now + 100)},  # Not expired
                }
            ]
        }

        records = dynamodb_retry_store.fetch_due()

        # Should filter out the claimed record
        assert len(records) == 0

    def test_fetch_due_respects_limit(self, dynamodb_retry_store):
        """Test that fetch_due respects the limit parameter."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb

        dynamodb_retry_store.fetch_due(limit=5)

        call_args = mock_dynamodb.query.call_args
        assert call_args[1]["Limit"] == 10  # 5 * 2 for filtering

    def test_fetch_due_returns_empty_on_classified_failure(self, dynamodb_retry_store):
        """A classified query failure returns no due records."""
        dynamodb_retry_store._mock_dynamodb.query.side_effect = _client_error("AccessDeniedException", "Query")

        assert dynamodb_retry_store.fetch_due() == []


class TestDynamoDBRetryStoreClaimRecord:
    """Tests for claim_record() method."""

    def test_claim_record_succeeds(self, dynamodb_retry_store):
        """Test successful record claim."""
        result = dynamodb_retry_store.claim_record("retry-1", "worker-1", 300)

        assert result is True
        dynamodb_retry_store._mock_dynamodb.update_item.assert_called_once()

    def test_claim_record_uses_conditional_expression(self, dynamodb_retry_store):
        """Test that claim uses conditional expression for atomicity."""
        dynamodb_retry_store.claim_record("retry-1", "worker-1", 300)

        call_args = dynamodb_retry_store._mock_dynamodb.update_item.call_args
        assert "ConditionExpression" in call_args[1]
        assert "attribute_not_exists(claim_worker)" in call_args[1]["ConditionExpression"]

    def test_claim_record_fails_on_condition_check(self, dynamodb_retry_store):
        """Test claim failure when condition check fails."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb

        # Simulate conditional check failure
        mock_dynamodb.update_item.side_effect = _client_error("ConditionalCheckFailedException", "UpdateItem")

        result = dynamodb_retry_store.claim_record("retry-1", "worker-1", 300)

        assert result is False

    def test_claim_record_returns_false_and_logs_mapped_failure(self, dynamodb_retry_store):
        """A mapped non-conditional claim failure returns false and emits an error event."""
        dynamodb_retry_store._mock_dynamodb.update_item.side_effect = _client_error("AccessDeniedException", "UpdateItem")

        with capture_logs() as entries:
            result = dynamodb_retry_store.claim_record("retry-1", "worker-1", 300)

        assert result is False
        failure_events = [entry for entry in entries if entry["event"] == "dynamodb_claim_failed"]
        assert failure_events
        assert failure_events[0]["error_code"] == "AccessDeniedException"

    def test_claim_record_propagates_unmapped_failure(self, dynamodb_retry_store):
        """An unmapped SDK failure is propagated unchanged."""
        error = _client_error("ValidationException", "UpdateItem")
        dynamodb_retry_store._mock_dynamodb.update_item.side_effect = error

        with pytest.raises(ClientError) as raised:
            dynamodb_retry_store.claim_record("retry-1", "worker-1", 300)

        assert raised.value is error


class TestDynamoDBRetryStoreMarkSuccess:
    """Tests for mark_success() method."""

    def test_mark_success_deletes_item(self, dynamodb_retry_store):
        """Test that mark_success deletes the item."""
        dynamodb_retry_store.mark_success("retry-1")

        call_args = dynamodb_retry_store._mock_dynamodb.delete_item.call_args
        assert call_args[1]["TableName"] == "test-retry-table"
        assert call_args[1]["Key"] == {"record_id": {"S": "retry-1"}}

    def test_mark_success_raises_runtime_error_on_classified_failure(self, dynamodb_retry_store):
        """A classified delete failure is surfaced as a runtime error."""
        dynamodb_retry_store._mock_dynamodb.delete_item.side_effect = _client_error("AccessDeniedException", "DeleteItem")

        with pytest.raises(RuntimeError, match="Failed to mark success"):
            dynamodb_retry_store.mark_success("retry-1")


class TestDynamoDBRetryStoreMarkPermanentFailure:
    """Tests for mark_permanent_failure() method."""

    def test_mark_permanent_failure_updates_status(self, dynamodb_retry_store):
        """Test that mark_permanent_failure updates status to DLQ."""
        dynamodb_retry_store.mark_permanent_failure("retry-1", "Error message")

        mock_dynamodb = dynamodb_retry_store._mock_dynamodb
        mock_dynamodb.update_item.assert_called_once()

        call_args = mock_dynamodb.update_item.call_args
        # Check that DLQ is in the expression values
        expr_values = call_args[1]["ExpressionAttributeValues"]
        assert any("DLQ" in str(v) for v in expr_values.values())

    def test_mark_permanent_failure_removes_claim(self, dynamodb_retry_store):
        """Test that mark_permanent_failure removes claim."""
        dynamodb_retry_store.mark_permanent_failure("retry-1")

        call_args = dynamodb_retry_store._mock_dynamodb.update_item.call_args
        assert "REMOVE claim_worker" in call_args[1]["UpdateExpression"]

    def test_mark_permanent_failure_raises_runtime_error_on_classified_failure(self, dynamodb_retry_store):
        """A classified DLQ write failure is surfaced as a runtime error."""
        dynamodb_retry_store._mock_dynamodb.update_item.side_effect = _client_error("AccessDeniedException", "UpdateItem")

        with pytest.raises(RuntimeError, match="Failed to mark permanent failure"):
            dynamodb_retry_store.mark_permanent_failure("retry-1")


class TestDynamoDBRetryStoreIncrementAttempt:
    """Tests for increment_attempt() method."""

    def test_increment_attempt_gets_current_record(self, dynamodb_retry_store):
        """Test that increment_attempt fetches current record."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb

        mock_dynamodb.get_item.return_value = {
            "Item": {
                "record_id": {"S": "retry-1"},
                "attempts": {"N": "2"},
            }
        }

        dynamodb_retry_store.increment_attempt("retry-1", "Error")

        mock_dynamodb.get_item.assert_called_once()
        call_args = mock_dynamodb.get_item.call_args
        assert call_args[1]["Key"] == {"record_id": {"S": "retry-1"}}

    def test_increment_attempt_moves_to_dlq_at_max(self, dynamodb_retry_store):
        """Test that increment_attempt moves to DLQ at max attempts."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb

        # At max attempts (3 total, so 2 current becomes 3 after increment)
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "record_id": {"S": "retry-1"},
                "attempts": {"N": "4"},  # Will be 5 after increment, >= max
            }
        }

        dynamodb_retry_store.increment_attempt("retry-1", "Final error")

        # Should call update_item to move to DLQ (via mark_permanent_failure)
        # The second update_item call should be for moving to DLQ
        assert mock_dynamodb.update_item.call_count >= 1

    def test_increment_attempt_releases_claim(self, dynamodb_retry_store):
        """Test that increment_attempt releases claim."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb

        mock_dynamodb.get_item.return_value = {
            "Item": {
                "record_id": {"S": "retry-1"},
                "attempts": {"N": "1"},
            }
        }

        dynamodb_retry_store.increment_attempt("retry-1")

        call_args = mock_dynamodb.update_item.call_args
        assert "REMOVE claim_worker" in call_args[1]["UpdateExpression"]

    def test_increment_attempt_does_nothing_when_item_is_missing(self, dynamodb_retry_store):
        """A missing read result is treated as a non-fatal no-op."""
        dynamodb_retry_store._mock_dynamodb.get_item.return_value = {}

        dynamodb_retry_store.increment_attempt("retry-1", "Error")

        dynamodb_retry_store._mock_dynamodb.update_item.assert_not_called()

    def test_increment_attempt_does_nothing_on_classified_read_failure(self, dynamodb_retry_store):
        """A classified read failure is logged and does not issue a write."""
        dynamodb_retry_store._mock_dynamodb.get_item.side_effect = _client_error("AccessDeniedException", "GetItem")

        with capture_logs() as entries:
            dynamodb_retry_store.increment_attempt("retry-1", "Error")

        assert any(
            entry["event"] == "retry_record_not_found_for_increment" and entry["error_code"] == "AccessDeniedException"
            for entry in entries
        )
        dynamodb_retry_store._mock_dynamodb.update_item.assert_not_called()

    def test_increment_attempt_raises_runtime_error_on_classified_write_failure(self, dynamodb_retry_store):
        """A classified increment write failure is surfaced as a runtime error."""
        dynamodb_retry_store._mock_dynamodb.get_item.return_value = {
            "Item": {"record_id": {"S": "retry-1"}, "attempts": {"N": "1"}}
        }
        dynamodb_retry_store._mock_dynamodb.update_item.side_effect = _client_error("AccessDeniedException", "UpdateItem")

        with pytest.raises(RuntimeError, match="Failed to increment attempt"):
            dynamodb_retry_store.increment_attempt("retry-1", "Error")


class TestDynamoDBRetryStoreGetStats:
    """Tests for get_stats() method."""

    def test_get_stats_queries_active_and_dlq(self, dynamodb_retry_store):
        """Test that get_stats queries both ACTIVE and DLQ records."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb
        paginator = mock_dynamodb.get_paginator.return_value
        paginator.paginate.side_effect = [
            [{"Count": 3}, {"Count": 2}],
            [{"Count": 4}],
        ]

        stats = dynamodb_retry_store.get_stats()

        assert mock_dynamodb.get_paginator.call_count == 2
        assert paginator.paginate.call_count == 2
        assert all(call.kwargs["Select"] == "COUNT" for call in paginator.paginate.call_args_list)
        assert stats["active_records"] == 5
        assert stats["dlq_records"] == 4

    def test_get_stats_returns_zero_on_error(self, dynamodb_retry_store):
        """Test that get_stats returns zeros on error."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb
        mock_dynamodb.get_paginator.return_value.paginate.side_effect = _client_error("AccessDeniedException", "Query")

        stats = dynamodb_retry_store.get_stats()

        assert stats["active_records"] == 0
        assert stats["claimed_records"] == 0
        assert stats["dlq_records"] == 0


class TestDynamoDBRetryStoreGetDlqEntries:
    """Tests for get_dlq_entries() method."""

    def test_get_dlq_entries_queries_dlq_status(self, dynamodb_retry_store):
        """Test that get_dlq_entries queries DLQ status."""
        mock_dynamodb = dynamodb_retry_store._mock_dynamodb

        now = datetime.now(UTC)
        mock_dynamodb.query.return_value = {
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

        entries = dynamodb_retry_store.get_dlq_entries()

        mock_dynamodb.query.assert_called_once()
        call_args = mock_dynamodb.query.call_args
        assert call_args[1]["TableName"] == "test-retry-table"
        assert call_args[1]["IndexName"] == "status-next_retry_at-index"

        assert len(entries) == 1
        assert entries[0].id == "retry-1"
        assert entries[0].last_error == "Max attempts reached"

    def test_get_dlq_entries_returns_empty_on_classified_failure(self, dynamodb_retry_store):
        """A classified DLQ query failure returns no entries."""
        dynamodb_retry_store._mock_dynamodb.query.side_effect = _client_error("AccessDeniedException", "Query")

        assert dynamodb_retry_store.get_dlq_entries() == []
