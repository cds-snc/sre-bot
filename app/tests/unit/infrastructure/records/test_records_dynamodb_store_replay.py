"""Replay safety of DynamoDBRecordStore.put_if_not_exists against the SDK's own retry.

A real boto3 DynamoDB client built with static dummy credentials is wrapped in
botocore.stub.Stubber, which validates each request and modeled error against
the service model and asserts the exact parameters. The per-call write token is
fixed through the store's token seam. A lost response is modeled as the
condition failure the retried request meets: its ALL_OLD item carries this
call's token when the first attempt landed, another token or none when another
writer created the item.
"""

from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from botocore.exceptions import EndpointConnectionError
from botocore.stub import Stubber
from structlog.testing import capture_logs

import infrastructure.records.service as service_module
from contracts.operations.status import OperationStatus
from contracts.records import KeySchema, RecordTable
from infrastructure.records.service import DynamoDBRecordStore

pytestmark = pytest.mark.unit

TABLE = RecordTable(name="things", key=KeySchema(partition="pk", sort="sk"))
TOKEN = "a" * 32
OTHER_TOKEN = "b" * 32


@pytest.fixture
def client() -> Any:
    return boto3.client("dynamodb", region_name="ca-central-1", aws_access_key_id="testing", aws_secret_access_key="testing")


@pytest.fixture
def stubber(client: Any) -> Iterator[Stubber]:
    with Stubber(client) as stub:
        yield stub
        stub.assert_no_pending_responses()


@pytest.fixture
def store(client: Any, monkeypatch: pytest.MonkeyPatch) -> DynamoDBRecordStore:
    monkeypatch.setattr(service_module, "_new_write_token", lambda: TOKEN)
    return DynamoDBRecordStore(dynamodb=client)


def _put_params() -> dict[str, Any]:
    return {
        "TableName": "things",
        "Item": {"pk": {"S": "a"}, "sk": {"S": "1"}, "value": {"N": "3"}, "_rs_write_token": {"S": TOKEN}},
        "ConditionExpression": "attribute_not_exists(#pk)",
        "ExpressionAttributeNames": {"#pk": "pk"},
        "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
    }


def _condition_failed(stubber: Stubber, existing: dict[str, Any] | None) -> None:
    stubber.add_client_error(
        "put_item",
        service_error_code="ConditionalCheckFailedException",
        service_message="The conditional request failed",
        http_status_code=400,
        expected_params=_put_params(),
        modeled_fields={"Item": existing} if existing is not None else None,
    )


def test_a_first_write_is_created_with_the_token_and_the_old_item_request(store: DynamoDBRecordStore, stubber: Stubber) -> None:
    stubber.add_response("put_item", {}, _put_params())

    result = store.put_if_not_exists(TABLE, {"pk": "a", "sk": "1", "value": 3, "empty": None})

    assert (result.is_success, result.data) == (True, True)


def test_a_retried_write_that_already_landed_is_created(store: DynamoDBRecordStore, stubber: Stubber) -> None:
    """The stored item carries this call's token, so the condition failure is the call's own first attempt."""
    _condition_failed(stubber, {"pk": {"S": "a"}, "sk": {"S": "1"}, "_rs_write_token": {"S": TOKEN}})

    with capture_logs() as logs:
        result = store.put_if_not_exists(TABLE, {"pk": "a", "sk": "1", "value": 3})

    assert (result.is_success, result.data) == (True, True)
    resolved = [log for log in logs if log["event"] == "records_put_if_not_exists_replay_resolved"]
    assert [(log["table"], log["operation"], log["key"]) for log in resolved] == [
        ("things", "put_if_not_exists", {"pk": "a", "sk": "1"})
    ]
    assert TOKEN not in str(logs)


@pytest.mark.parametrize(
    "existing",
    [
        {"pk": {"S": "a"}, "sk": {"S": "1"}, "_rs_write_token": {"S": OTHER_TOKEN}},
        {"pk": {"S": "a"}, "sk": {"S": "1"}},
        None,
    ],
    ids=["another-writer", "written-without-token", "no-old-item"],
)
def test_an_item_another_writer_created_already_exists(
    store: DynamoDBRecordStore, stubber: Stubber, existing: dict[str, Any] | None
) -> None:
    _condition_failed(stubber, existing)

    result = store.put_if_not_exists(TABLE, {"pk": "a", "sk": "1", "value": 3})

    assert (result.is_success, result.data) == (True, False)


def test_another_client_error_is_classified(store: DynamoDBRecordStore, stubber: Stubber) -> None:
    stubber.add_client_error(
        "put_item", service_error_code="AccessDeniedException", http_status_code=400, expected_params=_put_params()
    )

    with capture_logs() as logs:
        result = store.put_if_not_exists(TABLE, {"pk": "a", "sk": "1", "value": 3})

    assert not result.is_success
    assert result.error_code == "AccessDeniedException"
    errors = [log for log in logs if log["event"] == "records_put_if_not_exists_error"]
    assert [(log["operation"], log["key"]) for log in errors] == [("put_if_not_exists", {"pk": "a", "sk": "1"})]


def test_a_connection_failure_is_classified_without_raising(
    store: DynamoDBRecordStore, client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(**_: Any) -> None:
        raise EndpointConnectionError(endpoint_url="https://dynamodb.ca-central-1.amazonaws.com")

    monkeypatch.setattr(client, "put_item", fail)

    result = store.put_if_not_exists(TABLE, {"pk": "a", "sk": "1"})

    assert not result.is_success
    assert result.status is not OperationStatus.SUCCESS


def test_each_call_writes_a_fresh_token() -> None:
    """Two calls never share a token, so one caller's write cannot be taken for another's."""
    assert service_module._new_write_token() != service_module._new_write_token()
