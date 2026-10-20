"""Request shape and paging of DynamoDBRecordStore.read_all.

A real boto3 DynamoDB client built with static dummy credentials is wrapped in
botocore.stub.Stubber, which validates each Scan request and modeled error
against the service model and asserts the exact parameters. The stubbed pages
show the store follows ``LastEvaluatedKey``, asks for nothing past one item
over the cap, reads strongly consistently with no filter, projection, index or
segment, and classifies SDK errors instead of raising them.
"""

from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from botocore.stub import Stubber
from structlog.testing import capture_logs

from contracts.operations.status import OperationStatus
from contracts.records import READ_LIMIT_EXCEEDED, KeySchema, RecordTable
from infrastructure.records.service import DynamoDBRecordStore

pytestmark = pytest.mark.unit

TABLE = RecordTable(name="things", key=KeySchema(partition="pk"))


@pytest.fixture
def client() -> Any:
    return boto3.client("dynamodb", region_name="ca-central-1", aws_access_key_id="testing", aws_secret_access_key="testing")


@pytest.fixture
def stubber(client: Any) -> Iterator[Stubber]:
    with Stubber(client) as stub:
        yield stub
        stub.assert_no_pending_responses()


@pytest.fixture
def store(client: Any) -> DynamoDBRecordStore:
    return DynamoDBRecordStore(dynamodb=client)


def _item(pk: str) -> dict[str, Any]:
    return {"pk": {"S": pk}, "value": {"N": "1"}}


def _scan_params(start: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"TableName": "things", "ConsistentRead": True}
    if start is not None:
        params["ExclusiveStartKey"] = {"pk": {"S": start}}
    return params


def test_every_page_is_read_strongly_consistently_and_returned(store: DynamoDBRecordStore, stubber: Stubber) -> None:
    stubber.add_response(
        "scan", {"Items": [_item("a"), _item("b")], "LastEvaluatedKey": {"pk": {"S": "b"}}}, expected_params=_scan_params()
    )
    stubber.add_response("scan", {"Items": [_item("c")]}, expected_params=_scan_params(start="b"))

    result = store.read_all(TABLE, max_items=10)

    assert result.is_success
    assert result.data == [{"pk": "a", "value": 1}, {"pk": "b", "value": 1}, {"pk": "c", "value": 1}]


def test_paging_stops_once_the_table_holds_more_than_the_cap(store: DynamoDBRecordStore, stubber: Stubber) -> None:
    """Only the first page is stubbed: a request for the second would fail the stubber."""
    stubber.add_response(
        "scan",
        {"Items": [_item("a"), _item("b"), _item("c")], "LastEvaluatedKey": {"pk": {"S": "c"}}},
        expected_params=_scan_params(),
    )

    with capture_logs() as logs:
        result = store.read_all(TABLE, max_items=2)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == READ_LIMIT_EXCEEDED
    assert result.data is None
    assert {"event": "records_read_all_limit_exceeded", "table": "things", "max_items": 2}.items() <= logs[0].items()


def test_a_missing_table_is_a_classified_error(store: DynamoDBRecordStore, stubber: Stubber) -> None:
    stubber.add_client_error(
        "scan",
        service_error_code="ResourceNotFoundException",
        service_message="Requested resource not found",
        http_status_code=400,
        expected_params=_scan_params(),
    )

    with capture_logs() as logs:
        result = store.read_all(TABLE, max_items=10)

    assert not result.is_success
    assert result.error_code == "ResourceNotFoundException"
    assert any(log["event"] == "records_read_all_error" and log["table"] == "things" for log in logs)


def test_throttling_is_a_transient_error(store: DynamoDBRecordStore, stubber: Stubber) -> None:
    stubber.add_client_error(
        "scan",
        service_error_code="ProvisionedThroughputExceededException",
        service_message="Rate exceeded",
        http_status_code=400,
        expected_params=_scan_params(),
    )

    result = store.read_all(TABLE, max_items=10)

    assert result.status is OperationStatus.TRANSIENT_ERROR
