"""Unit tests for DynamoDBIdempotencyStore's direct DynamoDB calls."""

import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from infrastructure.idempotency.dynamodb import DynamoDBIdempotencyStore
from infrastructure.idempotency.protocol import ClaimResult
from infrastructure.idempotency.settings import IdempotencySettings

pytestmark = pytest.mark.unit


@pytest.fixture
def store_settings():
    settings = MagicMock(spec=IdempotencySettings)
    settings.IDEMPOTENCY_TTL_SECONDS = 3600
    settings.IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS = 300
    return settings


@pytest.fixture
def dynamodb_client():
    return MagicMock(spec=["put_item", "get_item", "delete_item"])


@pytest.fixture
def store(dynamodb_client, store_settings):
    return DynamoDBIdempotencyStore(
        dynamodb_client,
        idempotency_settings=store_settings,
        table_name="test_idempotency_store",
    )


class TestDynamoDBIdempotencyStoreClaimNewKey:
    def test_claim_new_key_issues_single_conditional_put(self, dynamodb_client, store):
        dynamodb_client.put_item.return_value = {}

        outcome = store.claim("feature:intent:new-key")

        assert outcome.result is ClaimResult.NEW
        assert dynamodb_client.put_item.call_count == 1
        call_kwargs = dynamodb_client.put_item.call_args.kwargs
        assert call_kwargs["TableName"] == "test_idempotency_store"
        condition_expression = call_kwargs.get("ConditionExpression", "")
        assert "attribute_not_exists" in condition_expression
        dynamodb_client.get_item.assert_not_called()


class TestDynamoDBIdempotencyStoreClaimConflict:
    def test_claim_on_completed_record_returns_completed_with_outcome(self, dynamodb_client, store):
        dynamodb_client.put_item.side_effect = ClientError(
            error_response={"Error": {"Code": "ConditionalCheckFailedException", "Message": "conflict"}},
            operation_name="PutItem",
        )
        recorded_outcome = {"status": "ok", "id": 42}
        dynamodb_client.get_item.return_value = {
            "Item": {
                "status": {"S": "COMPLETED"},
                "outcome_json": {"S": json.dumps(recorded_outcome)},
            }
        }

        outcome = store.claim("feature:intent:completed-key")

        assert outcome.result is ClaimResult.COMPLETED
        assert outcome.outcome == recorded_outcome
        dynamodb_client.get_item.assert_called_once_with(
            TableName="test_idempotency_store",
            Key={"idempotency_key": {"S": "feature:intent:completed-key"}},
            ConsistentRead=True,
        )

    def test_claim_on_in_progress_record_returns_in_progress(self, dynamodb_client, store):
        dynamodb_client.put_item.side_effect = ClientError(
            error_response={"Error": {"Code": "ConditionalCheckFailedException", "Message": "conflict"}},
            operation_name="PutItem",
        )
        dynamodb_client.get_item.return_value = {
            "Item": {"status": {"S": "IN_PROGRESS"}},
        }

        outcome = store.claim("feature:intent:in-progress-key")

        assert outcome.result is ClaimResult.IN_PROGRESS

    def test_claim_mapped_non_conditional_error_raises_runtime_error(self, dynamodb_client, store):
        dynamodb_client.put_item.side_effect = ClientError(
            error_response={"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            operation_name="PutItem",
        )

        with pytest.raises(RuntimeError, match="^Failed to claim idempotency key"):
            store.claim("feature:intent:mapped-error")

    def test_claim_unmapped_client_error_propagates_unchanged(self, dynamodb_client, store):
        client_error = ClientError(
            error_response={"Error": {"Code": "InternalServerError", "Message": "boom"}},
            operation_name="PutItem",
        )
        dynamodb_client.put_item.side_effect = client_error

        with pytest.raises(ClientError) as exc_info:
            store.claim("feature:intent:unmapped-error")

        assert exc_info.value is client_error


class TestDynamoDBIdempotencyStoreComplete:
    def test_complete_writes_completed_status_outcome_json_and_ttl(self, dynamodb_client, store):
        dynamodb_client.put_item.return_value = {}

        store.complete("feature:intent:key", {"status": "ok"})

        call_kwargs = dynamodb_client.put_item.call_args.kwargs
        assert call_kwargs["TableName"] == "test_idempotency_store"
        item = call_kwargs["Item"]
        assert item["status"]["S"] == "COMPLETED"
        assert json.loads(item["outcome_json"]["S"]) == {"status": "ok"}
        assert "ttl" in item


class TestDynamoDBIdempotencyStoreRelease:
    def test_release_deletes_the_record(self, dynamodb_client, store):
        dynamodb_client.delete_item.return_value = {}

        store.release("feature:intent:key")

        dynamodb_client.delete_item.assert_called_once_with(
            TableName="test_idempotency_store",
            Key={"idempotency_key": {"S": "feature:intent:key"}},
        )
