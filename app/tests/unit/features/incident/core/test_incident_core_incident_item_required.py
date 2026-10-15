"""Behavior tests for the end-state incident item parser: required values.

Pure function tests on plain dicts shaped like stored items, no store involved.
A required value that cannot be read makes the whole item a classified
INCIDENT_RECORD_UNREADABLE result, never an exception, and the log names the
incident and the field so the item can be fixed by hand.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.incident_items import parse_incident_item

pytestmark = pytest.mark.unit

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
    }
    item.update(overrides)
    return {key: value for key, value in item.items() if value is not None}


def test_a_minimal_end_state_item_reads_as_the_declared_incident() -> None:
    """The required attributes alone make a readable incident, named after the record fields."""
    result = parse_incident_item(_item())

    assert result.is_success
    incident = result.data
    assert incident is not None
    assert incident.id == INCIDENT_ID
    assert incident.status is IncidentStatus.OPEN
    assert incident.declared_by == "U0DECLARER"
    assert incident.declared_at == datetime(2026, 10, 15, 14, 0, tzinfo=UTC)
    assert incident.security_incident is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", None),
        ("id", "  "),
        ("title", None),
        ("title", ""),
        ("title", 7),
        ("status", None),
        ("status", "open"),
        ("status", "Investigating"),
        ("declared_by", None),
        ("declared_by", " "),
        ("declared_at", None),
        ("declared_at", "2026-10-15T14:00:00"),
        ("declared_at", "yesterday"),
        ("security_incident", None),
        ("security_incident", "true"),
        ("security_incident", Decimal(1)),
    ],
)
def test_an_unreadable_required_value_makes_the_item_unreadable(field: str, value: object) -> None:
    """Missing, blank, wrongly typed or not exactly a known value: classified, logged with id and field, never raised."""
    with capture_logs() as logs:
        result = parse_incident_item(_item(**{field: value}))

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE
    assert result.data is None
    events = [log for log in logs if log["event"] == "incident_record_unreadable"]
    assert len(events) == 1
    assert events[0]["field"] == field
    if field != "id":
        assert events[0]["incident_id"] == INCIDENT_ID


def test_an_unmatched_status_logs_the_stored_value() -> None:
    """Status is strict, so the stored value is logged for the hand fix."""
    with capture_logs() as logs:
        parse_incident_item(_item(status="reviewed"))

    assert [log["value"] for log in logs if log["event"] == "incident_record_unreadable"] == ["reviewed"]


def test_the_message_is_generic() -> None:
    """No stored value or field name reaches the caller's message."""
    result = parse_incident_item(_item(status="reviewed"))

    assert result.message is not None
    assert "reviewed" not in result.message
    assert "status" not in result.message
