"""Unit tests for DynamoDBIdempotencyStore's direct DynamoDB calls."""

import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from infrastructure.idempotency.dynamodb import DynamoDBIdempotencyStore
from infrastructure.idempotency.protocol import ClaimResult
from infrastructure.idempotency.settings import IdempotencySettings

pytestmark = pytest.mark.unit

FOREIGN_CLAIM_TOKEN = "0" * 32


def client_error(code: str, operation_name: str) -> ClientError:
    """Build the botocore error a stubbed DynamoDB call raises."""
    return ClientError(
        error_response={"Error": {"Code": code, "Message": code}},
        operation_name=operation_name,
    )


def conditional_check_failed() -> ClientError:
    """The error a losing conditional PutItem raises, which sends claim() to the re-read."""
    return client_error("ConditionalCheckFailedException", "PutItem")


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

    def test_claim_writes_a_distinct_claim_token_per_call(self, dynamodb_client, store):
        """The token is per call, not per store, so one caller can never match another's claim."""
        dynamodb_client.put_item.return_value = {}

        store.claim("feature:intent:first-key")
        store.claim("feature:intent:second-key")

        tokens = [call.kwargs["Item"]["claim_token"]["S"] for call in dynamodb_client.put_item.call_args_list]
        assert all(tokens), "every claim must stamp a token"
        assert tokens[0] != tokens[1]


class TestDynamoDBIdempotencyStoreClaimConflict:
    def test_claim_on_completed_record_returns_completed_with_outcome(self, dynamodb_client, store):
        dynamodb_client.put_item.side_effect = conditional_check_failed()
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

    def test_claim_replaying_its_own_conditional_put_returns_new(self, dynamodb_client, store):
        """A lost response makes the SDK resend the identical body, so the replay meets its own record.

        The re-read echoes back the token the store actually sent rather than a fixed
        value, so the test cannot pass by accident if token generation changes.
        """
        dynamodb_client.put_item.side_effect = conditional_check_failed()

        def echo_own_token(**_kwargs):
            own_token = dynamodb_client.put_item.call_args.kwargs["Item"]["claim_token"]["S"]
            return {"Item": {"status": {"S": "IN_PROGRESS"}, "claim_token": {"S": own_token}}}

        dynamodb_client.get_item.side_effect = echo_own_token

        outcome = store.claim("feature:intent:replayed-key")

        assert outcome.result is ClaimResult.NEW

    def test_claim_on_in_progress_record_with_another_token_returns_in_progress(self, dynamodb_client, store):
        """A token that is not ours is a real contender, not our own replay."""
        dynamodb_client.put_item.side_effect = conditional_check_failed()
        dynamodb_client.get_item.return_value = {
            "Item": {"status": {"S": "IN_PROGRESS"}, "claim_token": {"S": FOREIGN_CLAIM_TOKEN}},
        }

        outcome = store.claim("feature:intent:contended-key")

        assert outcome.result is ClaimResult.IN_PROGRESS

    def test_claim_on_in_progress_record_without_a_token_returns_in_progress(self, dynamodb_client, store):
        """A record written before claim tokens existed must not be mistaken for our own."""
        dynamodb_client.put_item.side_effect = conditional_check_failed()
        dynamodb_client.get_item.return_value = {
            "Item": {"status": {"S": "IN_PROGRESS"}},
        }

        outcome = store.claim("feature:intent:in-progress-key")

        assert outcome.result is ClaimResult.IN_PROGRESS

    def test_claim_returns_in_progress_when_the_contended_re_read_fails(self, dynamodb_client, store):
        """A classified read failure fails closed: an unreadable store is treated as still held.

        Our conditional put has already failed, so some record exists; being unable to
        read it is not grounds to claim the key.
        """
        dynamodb_client.put_item.side_effect = conditional_check_failed()
        dynamodb_client.get_item.side_effect = client_error("ProvisionedThroughputExceededException", "GetItem")

        outcome = store.claim("feature:intent:unreadable-key")

        assert outcome.result is ClaimResult.IN_PROGRESS

    def test_claim_propagates_an_unclassified_re_read_error(self, dynamodb_client, store):
        """Only classified failures fail closed; an unknown code is not evidence of contention."""
        dynamodb_client.put_item.side_effect = conditional_check_failed()
        read_error = client_error("ValidationException", "GetItem")
        dynamodb_client.get_item.side_effect = read_error

        with pytest.raises(ClientError) as exc_info:
            store.claim("feature:intent:unclassified-read-error")

        assert exc_info.value is read_error

    def test_claim_mapped_non_conditional_error_raises_runtime_error(self, dynamodb_client, store):
        dynamodb_client.put_item.side_effect = client_error("AccessDeniedException", "PutItem")

        with pytest.raises(RuntimeError, match="^Failed to claim idempotency key"):
            store.claim("feature:intent:mapped-error")

    def test_claim_unmapped_client_error_propagates_unchanged(self, dynamodb_client, store):
        put_error = client_error("ValidationException", "PutItem")
        dynamodb_client.put_item.side_effect = put_error

        with pytest.raises(ClientError) as exc_info:
            store.claim("feature:intent:unmapped-error")

        assert exc_info.value is put_error


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
