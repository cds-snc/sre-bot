"""Unit tests for DynamoDBIdempotencyStore.

Mocks infrastructure.idempotency.dynamodb.put_item/get_item/delete_item
directly (fast, no I/O) to pin the conditional-write contract: claim()
must use a single conditional PutItem, never a get-then-put chain.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from infrastructure.idempotency.dynamodb import DynamoDBIdempotencyStore
from infrastructure.idempotency.protocol import ClaimResult
from infrastructure.idempotency.settings import IdempotencySettings
from infrastructure.operations.result import OperationResult, OperationStatus

pytestmark = pytest.mark.unit


@pytest.fixture
def store_settings():
    settings = MagicMock(spec=IdempotencySettings)
    settings.IDEMPOTENCY_TTL_SECONDS = 3600
    settings.IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS = 300
    return settings


@pytest.fixture
def store(store_settings):
    return DynamoDBIdempotencyStore(idempotency_settings=store_settings, table_name="test_idempotency_store")


class TestDynamoDBIdempotencyStoreClaimNewKey:
    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_claim_new_key_issues_single_conditional_put(self, mock_put_item, store):
        mock_put_item.return_value = OperationResult(status=OperationStatus.SUCCESS, message="stored")

        outcome = store.claim("feature:intent:new-key")

        assert outcome.result is ClaimResult.NEW
        assert mock_put_item.call_count == 1
        call_kwargs = mock_put_item.call_args.kwargs
        condition_expression = call_kwargs.get("ConditionExpression", "")
        assert "attribute_not_exists" in condition_expression

    @patch("infrastructure.idempotency.dynamodb.get_item")
    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_claim_new_key_does_not_call_get_item(self, mock_put_item, mock_get_item, store):
        mock_put_item.return_value = OperationResult(status=OperationStatus.SUCCESS, message="stored")

        store.claim("feature:intent:new-key")

        mock_get_item.assert_not_called()


class TestDynamoDBIdempotencyStoreClaimConflict:
    @patch("infrastructure.idempotency.dynamodb.get_item")
    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_claim_on_completed_record_returns_completed_with_outcome(self, mock_put_item, mock_get_item, store):
        mock_put_item.return_value = OperationResult(
            status=OperationStatus.PERMANENT_ERROR,
            message="conflict",
            error_code="ConditionalCheckFailedException",
        )
        recorded_outcome = {"status": "ok", "id": 42}
        mock_get_item.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="found",
            data={
                "Item": {
                    "status": {"S": "COMPLETED"},
                    "outcome_json": {"S": json.dumps(recorded_outcome)},
                }
            },
        )

        outcome = store.claim("feature:intent:completed-key")

        assert outcome.result is ClaimResult.COMPLETED
        assert outcome.outcome == recorded_outcome

    @patch("infrastructure.idempotency.dynamodb.get_item")
    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_claim_on_in_progress_record_returns_in_progress(self, mock_put_item, mock_get_item, store):
        mock_put_item.return_value = OperationResult(
            status=OperationStatus.PERMANENT_ERROR,
            message="conflict",
            error_code="ConditionalCheckFailedException",
        )
        mock_get_item.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="found",
            data={"Item": {"status": {"S": "IN_PROGRESS"}}},
        )

        outcome = store.claim("feature:intent:in-progress-key")

        assert outcome.result is ClaimResult.IN_PROGRESS

    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_claim_raises_on_unexpected_error_code(self, mock_put_item, store):
        mock_put_item.return_value = OperationResult(
            status=OperationStatus.PERMANENT_ERROR,
            message="boom",
            error_code="InternalServerError",
        )

        with pytest.raises(RuntimeError):
            store.claim("feature:intent:unexpected-error")


class TestDynamoDBIdempotencyStoreComplete:
    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_complete_writes_completed_status_and_outcome_json(self, mock_put_item, store):
        mock_put_item.return_value = OperationResult(status=OperationStatus.SUCCESS, message="stored")

        store.complete("feature:intent:key", {"status": "ok"})

        call_kwargs = mock_put_item.call_args.kwargs
        item = call_kwargs["Item"]
        assert item["status"]["S"] == "COMPLETED"
        assert json.loads(item["outcome_json"]["S"]) == {"status": "ok"}


class TestDynamoDBIdempotencyStoreRelease:
    @patch("infrastructure.idempotency.dynamodb.delete_item")
    def test_release_deletes_the_record(self, mock_delete_item, store):
        mock_delete_item.return_value = OperationResult(status=OperationStatus.SUCCESS, message="deleted")

        store.release("feature:intent:key")

        mock_delete_item.assert_called_once()
