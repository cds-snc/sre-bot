"""Behavior tests for IncidentStore.read_security_flag.

The real store runs over InMemoryRecordStore. The flag is a required bool on
end-state items: true or false comes back as is, anything else makes the item
unreadable, and a store failure is never reported as false.
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import RecordStore
from features.incident.core.store import RecordIncidentStore, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

TABLE = incidents_table("incidents")
INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"


def _store(security_incident: object) -> RecordIncidentStore:
    records = InMemoryRecordStore()
    records.put(
        TABLE,
        {
            "id": INCIDENT_ID,
            "record_version": Decimal(1),
            "title": "Notify emails delayed",
            "status": "Open",
            "declared_by": "U0DECLARER",
            "declared_at": "2026-10-15T14:00:00.000000+00:00",
            "security_incident": security_incident,
        },
    )
    return RecordIncidentStore(records, TABLE)


@pytest.mark.parametrize("flag", [True, False])
def test_the_stored_bool_is_returned(flag: bool) -> None:
    result = _store(flag).read_security_flag(INCIDENT_ID)

    assert result.is_success
    assert result.data is flag


@pytest.mark.parametrize("stored", ["yes", Decimal(0), None])
def test_a_non_bool_flag_is_unreadable(stored: object) -> None:
    """There is no third state on an end-state item; a bad value is fixed by hand, never read as false."""
    result = _store(stored).read_security_flag(INCIDENT_ID)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE
    assert result.data is None


@pytest.mark.parametrize("incident_id", ["missing", "", " "])
def test_a_missing_or_blank_incident_is_not_an_incident(incident_id: str) -> None:
    result = _store(True).read_security_flag(incident_id)

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == ErrorCode.NOT_AN_INCIDENT


def test_a_store_failure_is_classified_and_never_false() -> None:
    records = MagicMock(spec=RecordStore)
    records.get.return_value = OperationResult.error(
        OperationStatus.PERMANENT_ERROR, message="AccessDenied", error_code="FORBIDDEN"
    )

    result = RecordIncidentStore(records, TABLE).read_security_flag(INCIDENT_ID)

    assert (result.status, result.error_code, result.data) == (OperationStatus.PERMANENT_ERROR, "FORBIDDEN", None)
