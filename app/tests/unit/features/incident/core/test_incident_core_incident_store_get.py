"""Behavior tests for IncidentStore.get over the records contract.

Runs RecordIncidentStore over InMemoryRecordStore with items shaped as the
writers store them; store failures come from a RecordStore stub returning an
error result with provider text, to check it never reaches the caller.
"""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import RecordStore
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import Severity
from features.incident.core.store import IncidentStore, RecordIncidentStore, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

TABLE = incidents_table("incidents")
TENANTS = {WorkplaceSystem.SLACK: "T0SLACK"}
INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"


def _item(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": INCIDENT_ID,
        "record_version": Decimal(1),
        "title": "Notify emails delayed",
        "status": "Open",
        "declared_by": "U0DECLARER",
        "declared_at": "2026-10-15T14:00:00.000000+00:00",
        "security_incident": False,
        "severity": Decimal(2),
    }
    item.update(overrides)
    return {key: value for key, value in item.items() if value is not None}


def _store(*items: dict[str, Any]) -> RecordIncidentStore:
    records = InMemoryRecordStore()
    for item in items:
        assert records.put(TABLE, item).is_success
    return RecordIncidentStore(records, TABLE, TENANTS)


def test_the_store_satisfies_the_protocol() -> None:
    assert isinstance(_store(), IncidentStore)


def test_a_stored_end_state_item_reads_as_the_incident() -> None:
    result = _store(_item()).get(INCIDENT_ID)

    assert result.is_success
    assert result.data is not None
    assert result.data.id == INCIDENT_ID
    assert result.data.title == "Notify emails delayed"
    assert result.data.severity is Severity.SEV2


@pytest.mark.parametrize("incident_id", ["missing", "", "  "])
def test_a_missing_or_blank_id_is_not_an_incident(incident_id: str) -> None:
    result = _store(_item()).get(incident_id)

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == ErrorCode.NOT_AN_INCIDENT


def test_a_store_failure_is_classified_with_a_generic_message() -> None:
    """The records store's status, code and retry hint pass through; its provider text does not."""
    records = MagicMock(spec=RecordStore)
    records.get.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR,
        message="ProvisionedThroughputExceeded: incidents",
        error_code="THROTTLED",
        retry_after=2.0,
    )

    with capture_logs() as logs:
        result = RecordIncidentStore(records, TABLE, TENANTS).get(INCIDENT_ID)

    assert (result.status, result.error_code, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, "THROTTLED", 2.0)
    assert result.message is not None
    assert "Provisioned" not in result.message
    failures = [log for log in logs if log["event"] == "incident_store_failed"]
    assert [(log["operation"], log["table"], log["error_code"]) for log in failures] == [("get", "incidents", "THROTTLED")]


def test_an_item_of_neither_shape_is_unreadable() -> None:
    """Without record_version the item goes through the legacy bridge, which finds no legacy name either."""
    with capture_logs() as logs:
        result = _store(_item(record_version=None)).get(INCIDENT_ID)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE
    unreadable = [log for log in logs if log["event"] == "incident_record_unreadable"]
    assert [(log["operation"], log["incident_id"], log["field"]) for log in unreadable] == [("get", INCIDENT_ID, "name")]


def test_an_unreadable_status_is_unreadable_with_the_stored_value_logged() -> None:
    with capture_logs() as logs:
        result = _store(_item(status="closed")).get(INCIDENT_ID)

    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE
    assert [(log["field"], log["value"]) for log in logs if log["event"] == "incident_record_unreadable"] == [
        ("status", "closed")
    ]
