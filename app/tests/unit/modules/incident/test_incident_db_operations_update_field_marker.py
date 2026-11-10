"""Behavior of update_incident_field against items with and without the record_version marker.

The DynamoDB adapter is replaced by ``MagicMock(spec=DynamoDBAdapter)`` returned
from a patched ``build_dynamodb_adapter``; the requests it receives are asserted.
A lost condition is the adapter's classified ``ConditionalCheckFailedException``
failure, as ``classify_aws_error`` reports it.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracts.operations import OperationResult, OperationStatus
from modules.incident import db_operations
from packages.aws_platform.adapters.dynamodb import DynamoDBAdapter

pytestmark = pytest.mark.unit


def _item(version: int | None) -> OperationResult[dict[str, Any] | None]:
    return OperationResult.success(data={} if version is None else {"record_version": {"N": str(version)}})


def _lost() -> OperationResult[None]:
    return OperationResult.error(
        OperationStatus.PERMANENT_ERROR, message="condition", error_code="ConditionalCheckFailedException"
    )


@pytest.fixture
def adapter():
    mock = MagicMock(spec=DynamoDBAdapter)
    mock.update_item.return_value = OperationResult.success()
    with (
        patch("modules.incident.db_operations.build_dynamodb_adapter", return_value=mock),
        patch("modules.incident.db_operations.log_activity") as activity,
    ):
        mock.activity = activity
        yield mock


@pytest.fixture
def logger_mock():
    with patch("modules.incident.db_operations.logger") as mock:
        mock.bind.return_value = mock
        yield mock


def test_an_item_without_the_marker_gets_the_plain_write_pinned_to_the_absent_marker(adapter) -> None:
    adapter.get_item.return_value = _item(None)

    db_operations.update_incident_field("inc-1", "severity", "sev-2", "U1")

    adapter.get_item.assert_called_once()
    request = adapter.update_item.call_args.kwargs
    assert request["UpdateExpression"] == "SET #severity = :severity"
    assert request["ExpressionAttributeValues"] == {":severity": {"S": "sev-2"}}
    assert request["ConditionExpression"] == "attribute_not_exists(record_version)"
    adapter.activity.assert_called_once()


def test_a_missing_item_is_written_as_before(adapter) -> None:
    adapter.get_item.return_value = OperationResult.success(data=None)

    db_operations.update_incident_field("inc-1", "severity", "sev-2", "U1")

    assert adapter.update_item.call_args.kwargs["UpdateExpression"] == "SET #severity = :severity"


def test_a_marker_two_item_gets_the_end_state_attribute_pinned_to_the_marker_it_read(adapter) -> None:
    adapter.get_item.return_value = _item(2)

    db_operations.update_incident_field("inc-1", "severity", "sev-2", "U1")

    request = adapter.update_item.call_args.kwargs
    assert request["Key"] == {"id": {"S": "inc-1"}}
    assert request["UpdateExpression"] == "SET #severity = :severity"
    assert request["ExpressionAttributeValues"] == {":severity": {"N": "2"}, ":seen": {"N": "2"}}
    assert request["ConditionExpression"] == "record_version = :seen"
    adapter.activity.assert_called_once()


def test_closing_a_marker_two_item_removes_the_open_index(adapter) -> None:
    adapter.get_item.return_value = _item(2)

    db_operations.update_incident_field("inc-1", "status", "Closed", "U1")

    request = adapter.update_item.call_args.kwargs
    assert request["UpdateExpression"] == "SET #status = :status REMOVE #open_bucket, #opened_at"
    assert request["ExpressionAttributeValues"] == {":status": {"S": "Closed"}, ":seen": {"N": "2"}}


def test_a_field_with_no_end_state_counterpart_is_written_under_its_legacy_name_on_a_marker_two_item(adapter) -> None:
    adapter.get_item.return_value = _item(2)

    db_operations.update_incident_field("inc-1", "retrospective_url", "https://r.example.test", "U1")

    request = adapter.update_item.call_args.kwargs
    assert request["UpdateExpression"] == "SET #retrospective_url = :retrospective_url"
    assert request["ConditionExpression"] == "record_version = :seen"


def test_a_lost_condition_re_reads_the_marker_and_retries_once(adapter, logger_mock) -> None:
    adapter.get_item.side_effect = [_item(None), _item(2)]
    adapter.update_item.side_effect = [_lost(), OperationResult.success()]

    db_operations.update_incident_field("inc-1", "severity", "sev-1", "U1")

    assert adapter.get_item.call_count == 2
    first, second = (call.kwargs for call in adapter.update_item.call_args_list)
    assert first["ConditionExpression"] == "attribute_not_exists(record_version)"
    assert second["ExpressionAttributeValues"][":severity"] == {"N": "1"}
    adapter.activity.assert_called_once()
    logger_mock.error.assert_not_called()


def test_a_second_lost_condition_is_logged_and_does_not_raise(adapter, logger_mock) -> None:
    adapter.get_item.return_value = _item(2)
    adapter.update_item.return_value = _lost()

    assert db_operations.update_incident_field("inc-1", "severity", "sev-1", "U1") is None

    assert adapter.update_item.call_count == 2
    logger_mock.error.assert_called_once_with(
        "incident_update_failed", status="permanent_error", error_code="ConditionalCheckFailedException", error="condition"
    )
    adapter.activity.assert_not_called()


def test_a_failed_marker_read_falls_back_to_the_write_pinned_to_the_absent_marker(adapter, logger_mock) -> None:
    adapter.get_item.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="boom", error_code="ThrottlingException"
    )

    db_operations.update_incident_field("inc-1", "severity", "sev-1", "U1")

    assert adapter.update_item.call_args.kwargs["ConditionExpression"] == "attribute_not_exists(record_version)"
    logger_mock.warning.assert_called_once()


def test_a_value_that_cannot_be_translated_is_logged_and_not_written(adapter, logger_mock) -> None:
    adapter.get_item.return_value = _item(2)

    db_operations.update_incident_field("inc-1", "severity", "critical", "U1")

    adapter.update_item.assert_not_called()
    logger_mock.error.assert_called_once()
