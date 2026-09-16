"""Behaviour of the incident persistence helpers over the DynamoDB adapter.

The adapter is replaced with ``MagicMock(spec=DynamoDBAdapter)`` returned from a
patched ``build_dynamodb_adapter``; each method returns an ``OperationResult``
so the helpers' branching on success, absence and failure is exercised without
botocore. Log assertions patch the module logger.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from infrastructure.operations import OperationResult, OperationStatus
from modules.incident import db_operations
from packages.aws_platform.adapters.dynamodb import DynamoDBAdapter


def _failure() -> OperationResult[Any]:
    return OperationResult.error(
        OperationStatus.TRANSIENT_ERROR,
        message="boom",
        error_code="ThrottlingException",
    )


FAILURE_FIELDS = {
    "status": OperationStatus.TRANSIENT_ERROR.value,
    "error_code": "ThrottlingException",
    "error": "boom",
}


@pytest.fixture
def adapter():
    """Patch the module's adapter factory with a spec'd mock and yield the mock."""
    mock = MagicMock(spec=DynamoDBAdapter)
    with patch("modules.incident.db_operations.build_dynamodb_adapter", return_value=mock) as factory:
        mock.factory = factory
        yield mock


@pytest.fixture
def logger_mock():
    with patch("modules.incident.db_operations.logger") as mock:
        mock.bind.return_value = mock
        yield mock


# -- create_incident -------------------------------------------------------


def test_create_incident(adapter, logger_mock):
    """A successful put returns the generated id that was written as the item key."""
    adapter.put_item.return_value = OperationResult.success()

    incident_data = {
        "id": "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "name": "name",
        "user_id": "user_id",
        "teams": ["teams"],
        "report_url": "report_url",
        "meet_url": "meet_url",
    }

    result = db_operations.create_incident(incident_data)

    assert isinstance(result, str)
    adapter.put_item.assert_called_once()
    call_kwargs = adapter.put_item.call_args.kwargs
    assert call_kwargs["TableName"] == "incidents"
    assert "Item" in call_kwargs


def test_create_incident_with_optional_args(adapter, logger_mock):
    """Optional fields are persisted on the item."""
    adapter.put_item.return_value = OperationResult.success()

    incident_data = {
        "id": "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "name": "name",
        "user_id": "user_id",
        "teams": ["teams"],
        "report_url": "report_url",
        "meet_url": "meet_url",
        "incident_commander": "incident_commander",
        "operations_lead": "operations_lead",
        "severity": "severity",
        "environment": "dev",
    }

    result = db_operations.create_incident(incident_data)

    assert isinstance(result, str)
    adapter.put_item.assert_called_once()


@patch("modules.incident.db_operations.logger")
def test_create_incident_with_invalid_data(mock_logger):
    """Invalid incident data raises ValueError."""
    incident_data = {
        "id": "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d",
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "report_url": "report_url",
        "meet_url": "meet_url",
    }

    with pytest.raises(ValueError, match="Invalid incident data"):
        db_operations.create_incident(incident_data)


def test_create_incident_already_exists(adapter, logger_mock):
    """When a duplicate incident exists, the existing id is returned and nothing is written."""
    with patch("modules.incident.db_operations.get_incident_by_channel_id") as mock_get:
        mock_get.return_value = {
            "id": {"S": "existing_id"},
            "channel_id": {"S": "bar"},
        }

        incident_data = {
            "id": "foo",
            "channel_id": "bar",
            "channel_name": "baz",
            "name": "qux",
            "user_id": "quux",
            "teams": ["corge"],
            "report_url": "grault",
            "meet_url": "garply",
        }

        result = db_operations.create_incident(incident_data)

        assert result == "existing_id"
        adapter.put_item.assert_not_called()


def test_create_incident_returns_none_and_logs_on_non_success_put(adapter, logger_mock):
    """A failed put returns None and logs the classified failure."""
    adapter.put_item.return_value = _failure()

    incident_data = {
        "id": "foo",
        "channel_id": "bar",
        "channel_name": "baz",
        "name": "qux",
        "user_id": "quux",
        "teams": ["corge"],
        "report_url": "grault",
        "meet_url": "garply",
    }

    result = db_operations.create_incident(incident_data)

    assert result is None
    logger_mock.error.assert_called_once_with("incident_creation_failed", **FAILURE_FIELDS)


def test_create_incident_logs_and_returns_none_on_unclassified_client_error(adapter, logger_mock):
    """An unclassified ClientError is logged with status='unclassified' and returns None."""
    adapter.put_item.side_effect = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "missing attribute"}},
        "PutItem",
    )

    incident_data = {
        "id": "foo",
        "channel_id": "bar",
        "channel_name": "baz",
        "name": "qux",
        "user_id": "quux",
        "teams": ["corge"],
        "report_url": "grault",
        "meet_url": "garply",
    }

    result = db_operations.create_incident(incident_data)

    assert result is None
    logger_mock.error.assert_called_once_with(
        "incident_creation_failed",
        status="unclassified",
        error_code="ValidationException",
        error="missing attribute",
    )


def test_create_incident_propagates_programmer_error(adapter, logger_mock):
    """Only SDK errors are swallowed; a programmer error still propagates."""
    adapter.put_item.side_effect = KeyError("bad call")

    incident_data = {
        "id": "foo",
        "channel_id": "bar",
        "channel_name": "baz",
        "name": "qux",
        "user_id": "quux",
        "teams": ["corge"],
        "report_url": "grault",
        "meet_url": "garply",
    }

    with pytest.raises(KeyError):
        db_operations.create_incident(incident_data)


def test_create_incident_propagates_when_duplicate_check_fails(adapter, logger_mock):
    """When the duplicate-check scan fails, the error is not caught."""
    with patch("modules.incident.db_operations.get_incident_by_channel_id") as mock_get:
        mock_get.side_effect = db_operations.IncidentStoreUnavailableError(
            OperationStatus.PERMANENT_ERROR,
            error_code="ValidationException",
        )

        incident_data = {
            "id": "foo",
            "channel_id": "bar",
            "channel_name": "baz",
            "name": "qux",
            "user_id": "quux",
            "teams": ["corge"],
            "report_url": "grault",
            "meet_url": "garply",
        }

        with pytest.raises(db_operations.IncidentStoreUnavailableError):
            db_operations.create_incident(incident_data)

        adapter.put_item.assert_not_called()


# -- list_incidents -----------------------------------------------------------


def test_list_incidents(adapter, logger_mock):
    """The full-table scan returns every item."""
    incident_item = {
        "id": {"S": "foo"},
        "channel_id": {"S": "bar"},
    }
    adapter.scan.return_value = OperationResult.success(data=[incident_item])

    result = db_operations.list_incidents()

    assert result == [incident_item]
    adapter.scan.assert_called_once_with(TableName="incidents", Select="ALL_ATTRIBUTES")


def test_list_incidents_empty(adapter, logger_mock):
    """An empty scan returns an empty list."""
    adapter.scan.return_value = OperationResult.success(data=[])

    result = db_operations.list_incidents()

    assert result == []


def test_list_incidents_raises_and_logs_on_non_success(adapter, logger_mock):
    """A failed scan raises IncidentStoreUnavailableError after logging the classified failure."""
    adapter.scan.return_value = _failure()

    with pytest.raises(db_operations.IncidentStoreUnavailableError) as exc_info:
        db_operations.list_incidents()

    assert exc_info.value.status is OperationStatus.TRANSIENT_ERROR
    assert exc_info.value.error_code == "ThrottlingException"
    logger_mock.error.assert_called_once_with("incident_list_failed", **FAILURE_FIELDS)


def test_list_incidents_raises_incident_store_unavailable_on_unclassified_client_error(adapter, logger_mock):
    """An unclassified ClientError is logged with status='unclassified' and re-raised as IncidentStoreUnavailableError."""
    adapter.scan.side_effect = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "validation failed"}},
        "Scan",
    )

    with pytest.raises(db_operations.IncidentStoreUnavailableError) as exc_info:
        db_operations.list_incidents()

    assert exc_info.value.status is OperationStatus.PERMANENT_ERROR
    assert exc_info.value.error_code == "ValidationException"
    assert exc_info.value.retry_after is None
    logger_mock.error.assert_called_once_with(
        "incident_list_failed",
        status="unclassified",
        error_code="ValidationException",
        error="validation failed",
    )


def test_list_incidents_propagates_programmer_error(adapter, logger_mock):
    """Only SDK errors are swallowed; a programmer error still propagates."""
    adapter.scan.side_effect = KeyError("bad call")

    with pytest.raises(KeyError):
        db_operations.list_incidents()


# -- update_incident_field --------------------------------------------------


def test_update_incident_field(adapter, logger_mock):
    """A successful update writes the field with the default type 'S'."""
    adapter.update_item.return_value = OperationResult.success()

    result = db_operations.update_incident_field("foo", "bar", "baz", "user_id")

    assert result is None
    adapter.update_item.assert_called_once()
    call_kwargs = adapter.update_item.call_args.kwargs
    assert call_kwargs["TableName"] == "incidents"
    assert call_kwargs["Key"] == {"id": {"S": "foo"}}
    assert call_kwargs["ExpressionAttributeValues"] == {":bar": {"S": "baz"}}


def test_update_incident_field_with_type(adapter, logger_mock):
    """The type parameter specifies the DynamoDB type."""
    adapter.update_item.return_value = OperationResult.success()

    db_operations.update_incident_field("foo", "bar", "baz", "user_id", type="M")

    adapter.update_item.assert_called_once()
    call_kwargs = adapter.update_item.call_args.kwargs
    assert call_kwargs["ExpressionAttributeValues"] == {":bar": {"M": "baz"}}


def test_update_incident_field_returns_none_and_logs_on_non_success(adapter, logger_mock):
    """A failed update returns None and logs the classified failure."""
    adapter.update_item.return_value = _failure()

    result = db_operations.update_incident_field("foo", "bar", "baz", "user_id")

    assert result is None
    logger_mock.error.assert_called_once_with("incident_update_failed", **FAILURE_FIELDS)


def test_update_incident_field_logs_and_returns_none_on_unclassified_client_error(adapter, logger_mock):
    """An unclassified ClientError is logged with status='unclassified' and returns None."""
    adapter.update_item.side_effect = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "bad value"}},
        "UpdateItem",
    )

    result = db_operations.update_incident_field("foo", "bar", "baz", "user_id")

    assert result is None
    logger_mock.error.assert_called_once_with(
        "incident_update_failed",
        status="unclassified",
        error_code="ValidationException",
        error="bad value",
    )


def test_update_incident_field_propagates_programmer_error(adapter, logger_mock):
    """Only SDK errors are swallowed; a programmer error still propagates."""
    adapter.update_item.side_effect = KeyError("bad call")

    with pytest.raises(KeyError):
        db_operations.update_incident_field("foo", "bar", "baz", "user_id")


def test_update_incident_field_protected_field_skips_write(adapter, logger_mock):
    """Protected fields (id, created_at) are not written."""
    result = db_operations.update_incident_field("foo", "id", "bar", "user_id")

    assert result is None
    adapter.update_item.assert_not_called()


# -- log_activity -----------------------------------------------------------


def test_log_activity_sends_update_item_with_retries_false(adapter, logger_mock):
    """log_activity uses retries=False and returns True on success."""
    adapter.update_item.return_value = OperationResult.success()

    result = db_operations.log_activity("incident-1", "message")

    assert result is True
    adapter.update_item.assert_called_once()
    call_kwargs = adapter.update_item.call_args.kwargs
    assert call_kwargs["retries"] is False


def test_log_activity_returns_false_and_logs_on_non_success(adapter, logger_mock):
    """A failed update returns False and logs the classified failure."""
    adapter.update_item.return_value = _failure()

    result = db_operations.log_activity("incident-1", "message")

    assert result is False
    logger_mock.error.assert_called_once_with("activity_log_failed", **FAILURE_FIELDS)


def test_log_activity_logs_and_returns_false_on_unclassified_client_error(adapter, logger_mock):
    """An unclassified ClientError is logged with status='unclassified' and returns False."""
    adapter.update_item.side_effect = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "bad message"}},
        "UpdateItem",
    )

    result = db_operations.log_activity("incident-1", "message")

    assert result is False
    logger_mock.error.assert_called_once_with(
        "activity_log_failed",
        status="unclassified",
        error_code="ValidationException",
        error="bad message",
    )


def test_log_activity_propagates_programmer_error(adapter, logger_mock):
    """Only SDK errors are swallowed; a programmer error still propagates."""
    adapter.update_item.side_effect = KeyError("bad call")

    with pytest.raises(KeyError):
        db_operations.log_activity("incident-1", "message")


# -- lookup_incident -------------------------------------------------------


def test_lookup_incident(adapter, logger_mock):
    """The scan filters on the field with a string AttributeValue and returns every item."""
    incident_item = {
        "id": {"S": "foo"},
        "channel_id": {"S": "bar"},
    }
    adapter.scan.return_value = OperationResult.success(data=[incident_item])

    result = db_operations.lookup_incident("channel_id", "bar")

    assert result == [incident_item]
    adapter.scan.assert_called_once_with(
        TableName="incidents",
        FilterExpression="channel_id = :channel_id",
        ExpressionAttributeValues={":channel_id": {"S": "bar"}},
    )


def test_lookup_incident_returns_empty_list(adapter, logger_mock):
    """An empty scan returns an empty list."""
    adapter.scan.return_value = OperationResult.success(data=[])

    result = db_operations.lookup_incident("channel_id", "bar")

    assert result == []


def test_lookup_incident_raises_and_logs_on_non_success(adapter, logger_mock):
    """A failed scan raises IncidentStoreUnavailableError after logging the classified failure."""
    adapter.scan.return_value = _failure()

    with pytest.raises(db_operations.IncidentStoreUnavailableError):
        db_operations.lookup_incident("channel_id", "bar")

    logger_mock.error.assert_called_once_with("incident_lookup_failed", field="channel_id", **FAILURE_FIELDS)


def test_lookup_incident_raises_incident_store_unavailable_on_unclassified_client_error(adapter, logger_mock):
    """An unclassified ClientError is logged with status='unclassified' and re-raised as IncidentStoreUnavailableError."""
    adapter.scan.side_effect = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "validation failed"}},
        "Scan",
    )

    with pytest.raises(db_operations.IncidentStoreUnavailableError) as exc_info:
        db_operations.lookup_incident("channel_id", "bar")

    assert exc_info.value.status is OperationStatus.PERMANENT_ERROR
    assert exc_info.value.error_code == "ValidationException"
    logger_mock.error.assert_called_once_with(
        "incident_lookup_failed",
        field="channel_id",
        status="unclassified",
        error_code="ValidationException",
        error="validation failed",
    )


def test_lookup_incident_propagates_programmer_error(adapter, logger_mock):
    """Only SDK errors are swallowed; a programmer error still propagates."""
    adapter.scan.side_effect = KeyError("bad call")

    with pytest.raises(KeyError):
        db_operations.lookup_incident("channel_id", "bar")


# -- get_incident_by_channel_id ------------------------------------------


def test_get_incident_by_channel_id(logger_mock):
    """lookup_incident returns a list; the first item is returned."""
    incident_item = {
        "id": {"S": "foo"},
        "channel_id": {"S": "bar"},
    }
    with patch("modules.incident.db_operations.lookup_incident") as mock_lookup:
        mock_lookup.return_value = [incident_item]

        result = db_operations.get_incident_by_channel_id("bar")

        assert result == incident_item
        mock_lookup.assert_called_once_with("channel_id", "bar")


def test_get_incident_by_channel_id_multiple_results(logger_mock):
    """When multiple incidents exist, the first is returned."""
    with patch("modules.incident.db_operations.lookup_incident") as mock_lookup:
        mock_lookup.return_value = [
            {"id": {"S": "foo"}},
            {"id": {"S": "baz"}},
        ]

        result = db_operations.get_incident_by_channel_id("bar")

        assert result == {"id": {"S": "foo"}}


def test_get_incident_by_channel_id_no_results(logger_mock):
    """An empty list returns None."""
    with patch("modules.incident.db_operations.lookup_incident") as mock_lookup:
        mock_lookup.return_value = []

        result = db_operations.get_incident_by_channel_id("bar")

        assert result is None


def test_get_incident_by_channel_id_propagates_when_lookup_fails(logger_mock):
    """When lookup_incident raises, the error is not caught."""
    with patch("modules.incident.db_operations.lookup_incident") as mock_lookup:
        mock_lookup.side_effect = db_operations.IncidentStoreUnavailableError(
            OperationStatus.PERMANENT_ERROR,
            error_code="ValidationException",
        )

        with pytest.raises(db_operations.IncidentStoreUnavailableError):
            db_operations.get_incident_by_channel_id("bar")
