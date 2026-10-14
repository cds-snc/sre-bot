"""Ownership checks on DynamoDBIdempotencyStore.complete() and release().

A real boto3 DynamoDB client built with static dummy credentials is wrapped in
botocore.stub.Stubber, which validates each request against the service model
and asserts its exact parameters. The tests pin the condition expressions that
gate complete and release on the caller's claim token, the mapping of a failed
condition to False, and the propagation of every other failure.
"""

from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import ANY, Stubber

from infrastructure.idempotency.dynamodb import DynamoDBIdempotencyStore
from infrastructure.idempotency.protocol import ClaimResult
from infrastructure.idempotency.settings import IdempotencySettings

pytestmark = pytest.mark.unit

TABLE_NAME = "test_idempotency_store"
KEY = "feature:intent:key"
CLAIM_TOKEN = "a" * 32


def _dynamodb_client() -> Any:
    """Build a real boto3 DynamoDB client with dummy static credentials."""
    return boto3.client(
        "dynamodb",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


@pytest.fixture
def client() -> Any:
    return _dynamodb_client()


@pytest.fixture
def store(client: Any) -> DynamoDBIdempotencyStore:
    settings = IdempotencySettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=300)
    return DynamoDBIdempotencyStore(client, idempotency_settings=settings, table_name=TABLE_NAME)


def _complete_params() -> dict[str, Any]:
    return {
        "TableName": TABLE_NAME,
        "Item": {
            "idempotency_key": {"S": KEY},
            "status": {"S": "COMPLETED"},
            "claim_token": {"S": CLAIM_TOKEN},
            "outcome_json": {"S": '{"status": "ok"}'},
            "completed_at": ANY,
            "ttl": ANY,
        },
        "ConditionExpression": "#claim_token = :claim_token",
        "ExpressionAttributeNames": {"#claim_token": "claim_token"},
        "ExpressionAttributeValues": {":claim_token": {"S": CLAIM_TOKEN}},
    }


def _release_params() -> dict[str, Any]:
    return {
        "TableName": TABLE_NAME,
        "Key": {"idempotency_key": {"S": KEY}},
        "ConditionExpression": "#claim_token = :claim_token AND #status = :in_progress",
        "ExpressionAttributeNames": {"#claim_token": "claim_token", "#status": "status"},
        "ExpressionAttributeValues": {
            ":claim_token": {"S": CLAIM_TOKEN},
            ":in_progress": {"S": "IN_PROGRESS"},
        },
    }


class TestComplete:
    def test_complete_puts_conditionally_on_the_claim_token_and_keeps_it(self, client, store):
        """The COMPLETED item keeps the token so a replayed complete still matches."""
        with Stubber(client) as stub:
            stub.add_response("put_item", {}, expected_params=_complete_params())

            assert store.complete(KEY, {"status": "ok"}, CLAIM_TOKEN) is True

    def test_complete_returns_false_when_the_condition_fails(self, client, store):
        with Stubber(client) as stub:
            stub.add_client_error(
                "put_item", service_error_code="ConditionalCheckFailedException", expected_params=_complete_params()
            )

            assert store.complete(KEY, {"status": "ok"}, CLAIM_TOKEN) is False

    def test_complete_raises_runtime_error_on_a_classified_failure(self, client, store):
        with Stubber(client) as stub:
            stub.add_client_error("put_item", service_error_code="ProvisionedThroughputExceededException")

            with pytest.raises(RuntimeError, match="^Failed to complete idempotency key"):
                store.complete(KEY, {"status": "ok"}, CLAIM_TOKEN)

    def test_complete_propagates_an_unclassified_error(self, client, store):
        with Stubber(client) as stub:
            stub.add_client_error("put_item", service_error_code="ValidationException")

            with pytest.raises(ClientError):
                store.complete(KEY, {"status": "ok"}, CLAIM_TOKEN)


class TestRelease:
    def test_release_deletes_only_an_in_progress_record_holding_the_claim_token(self, client, store):
        with Stubber(client) as stub:
            stub.add_response("delete_item", {}, expected_params=_release_params())

            assert store.release(KEY, CLAIM_TOKEN) is True

    def test_release_returns_false_when_the_condition_fails(self, client, store):
        with Stubber(client) as stub:
            stub.add_client_error(
                "delete_item", service_error_code="ConditionalCheckFailedException", expected_params=_release_params()
            )

            assert store.release(KEY, CLAIM_TOKEN) is False

    def test_release_raises_runtime_error_on_a_classified_failure(self, client, store, monkeypatch):
        monkeypatch.setattr(client, "delete_item", _raise(EndpointConnectionError(endpoint_url="https://dynamodb")))

        with pytest.raises(RuntimeError, match="^Failed to release idempotency key"):
            store.release(KEY, CLAIM_TOKEN)

    def test_release_propagates_an_unclassified_error(self, client, store):
        with Stubber(client) as stub:
            stub.add_client_error("delete_item", service_error_code="ValidationException")

            with pytest.raises(ClientError):
                store.release(KEY, CLAIM_TOKEN)


class TestOwnershipLostLogging:
    def test_lost_ownership_logs_a_warning_without_the_token(self, client, store, monkeypatch):
        """The token is a bearer secret for the claim, so it never reaches the logs."""
        warnings: list[tuple[str, dict[str, Any]]] = []
        monkeypatch.setattr(store, "log", _RecordingLogger(warnings))

        with Stubber(client) as stub:
            stub.add_client_error("delete_item", service_error_code="ConditionalCheckFailedException")
            store.release(KEY, CLAIM_TOKEN)

        assert warnings == [("claim_ownership_lost", {"key": KEY, "operation": "release"})]


class TestClaimReturnsToken:
    def test_new_claim_returns_the_token_it_wrote(self, client, store):
        with Stubber(client) as stub:
            stub.add_response(
                "put_item",
                {},
                expected_params={
                    "TableName": TABLE_NAME,
                    "Item": ANY,
                    "ConditionExpression": ANY,
                    "ExpressionAttributeNames": ANY,
                    "ExpressionAttributeValues": ANY,
                },
            )

            outcome = store.claim(KEY)

        assert outcome.result is ClaimResult.NEW
        assert outcome.claim_token is not None
        assert len(outcome.claim_token) == 32


def _raise(exc: Exception) -> Any:
    def _call(**_kwargs: Any) -> Any:
        raise exc

    return _call


class _RecordingLogger:
    """Captures warning events; the store's bound structlog logger is replaced wholesale."""

    def __init__(self, warnings: list[tuple[str, dict[str, Any]]]) -> None:
        self._warnings = warnings

    def warning(self, event: str, **kwargs: Any) -> None:
        self._warnings.append((event, kwargs))
