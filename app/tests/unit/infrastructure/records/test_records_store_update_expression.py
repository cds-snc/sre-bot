"""Unit tests for the UpdateItem request DynamoDBRecordStore.update sends.

A ``MagicMock`` client captures the single ``update_item`` call, so the
tests assert its exact shape: one UpdateExpression, a placeholder for every
attribute name, an existence condition, and no read before the write.
Condition failures are simulated with ``ClientError`` responses carrying or
omitting the old item, which is how the store tells a missing item from an
unmet guard.
"""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from contracts.operations.status import OperationStatus
from contracts.records import (
    IncrementAttribute,
    KeySchema,
    RecordTable,
    RemoveAttribute,
    SetAttribute,
)
from infrastructure.records.service import DynamoDBRecordStore

TABLE = RecordTable(name="my_table", key=KeySchema(partition="pk", sort="sk"))
KEY = {"pk": "a", "sk": "1"}

pytestmark = pytest.mark.unit


def _make_store() -> tuple[DynamoDBRecordStore, MagicMock]:
    dynamo = MagicMock()
    dynamo.update_item.return_value = {"Attributes": {"pk": {"S": "a"}, "sk": {"S": "1"}, "status": {"S": "open"}}}
    return DynamoDBRecordStore(dynamodb=dynamo), dynamo


def _condition_failed(item: dict[str, object] | None) -> ClientError:
    response: dict[str, object] = {"Error": {"Code": "ConditionalCheckFailedException", "Message": "failed"}}
    if item is not None:
        response["Item"] = item
    return ClientError(error_response=response, operation_name="UpdateItem")  # type: ignore[arg-type]


def test_mixed_changes_map_to_one_update_expression_with_placeholders() -> None:
    store, dynamo = _make_store()

    store.update(
        TABLE,
        KEY,
        [SetAttribute("status", "open"), IncrementAttribute("count", 3), RemoveAttribute("open_since")],
    )

    dynamo.get_item.assert_not_called()
    dynamo.update_item.assert_called_once()
    kwargs = dynamo.update_item.call_args.kwargs
    assert kwargs["TableName"] == "my_table"
    assert kwargs["Key"] == {"pk": {"S": "a"}, "sk": {"S": "1"}}
    assert kwargs["UpdateExpression"] == "SET #c0 = :v0, #c1 = if_not_exists(#c1, :zero) + :v1 REMOVE #c2"
    assert kwargs["ConditionExpression"] == "attribute_exists(#pk)"
    assert kwargs["ExpressionAttributeNames"] == {"#pk": "pk", "#c0": "status", "#c1": "count", "#c2": "open_since"}
    assert kwargs["ExpressionAttributeValues"] == {":v0": {"S": "open"}, ":v1": {"N": "3"}, ":zero": {"N": "0"}}
    assert kwargs["ReturnValues"] == "ALL_NEW"
    assert kwargs["ReturnValuesOnConditionCheckFailure"] == "ALL_OLD"


def test_remove_only_sends_no_expression_values() -> None:
    store, dynamo = _make_store()

    store.update(TABLE, KEY, [RemoveAttribute("open_since")])

    kwargs = dynamo.update_item.call_args.kwargs
    assert kwargs["UpdateExpression"] == "REMOVE #c0"
    assert "ExpressionAttributeValues" not in kwargs


def test_guard_is_appended_to_the_existence_condition() -> None:
    store, dynamo = _make_store()

    store.update(TABLE, KEY, [SetAttribute("status", "closed")], expected={"status": "open", "owner": None})

    kwargs = dynamo.update_item.call_args.kwargs
    assert kwargs["ConditionExpression"] == ("attribute_exists(#pk) AND #e0 = :e0 AND (attribute_not_exists(#e1) OR #e1 = :null)")
    assert kwargs["ExpressionAttributeNames"]["#e0"] == "status"
    assert kwargs["ExpressionAttributeNames"]["#e1"] == "owner"
    assert kwargs["ExpressionAttributeValues"][":e0"] == {"S": "open"}
    assert kwargs["ExpressionAttributeValues"][":null"] == {"NULL": True}


def test_applied_update_returns_the_deserialized_item() -> None:
    store, _ = _make_store()

    result = store.update(TABLE, KEY, [SetAttribute("status", "open")])

    assert result.is_success
    assert result.data == {"pk": "a", "sk": "1", "status": "open"}


def test_condition_failure_without_old_item_is_not_found() -> None:
    store, dynamo = _make_store()
    dynamo.update_item.side_effect = _condition_failed(None)

    result = store.update(TABLE, KEY, [SetAttribute("status", "open")])

    assert result.status == OperationStatus.NOT_FOUND


def test_condition_failure_with_old_item_is_an_unmet_guard() -> None:
    store, dynamo = _make_store()
    dynamo.update_item.side_effect = _condition_failed({"pk": {"S": "a"}, "sk": {"S": "1"}})

    result = store.update(TABLE, KEY, [SetAttribute("status", "open")], expected={"status": "new"})

    assert result.is_success
    assert result.data is None


def test_other_client_errors_are_mapped() -> None:
    store, dynamo = _make_store()
    dynamo.update_item.side_effect = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
        operation_name="UpdateItem",
    )

    result = store.update(TABLE, KEY, [SetAttribute("status", "open")])

    assert not result.is_success
    assert result.error_code == "ResourceNotFoundException"
