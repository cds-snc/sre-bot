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

from contracts.operations import OperationResult, OperationStatus
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
