"""Behavior tests for the end-state incident item parser: tolerant optional values.

Pure function tests on plain dicts shaped like stored items. An optional value
that cannot be read is dropped (not recorded, not assigned, not rated) and the
incident stays readable; the log names the incident, the field and the stored
value so the item can be fixed, and never carries the whole item.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from structlog.testing import capture_logs

from features.incident.common.vocabulary import IncidentRole, Severity
from features.incident.core.adapters.incident_items import parse_incident_item
from features.incident.core.domain import Incident

pytestmark = pytest.mark.unit

INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"
OPTIONAL_TIMES = ["detected_at", "impact_started_at", "impact_ended_at"]


def _item(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": INCIDENT_ID,
        "record_version": Decimal(1),
        "title": "Notify emails delayed",
        "status": "In Progress",
        "declared_by": "U0DECLARER",
        "declared_at": "2026-10-15T14:00:00.000000+00:00",
        "security_incident": True,
    }
    item.update(overrides)
    return item


def _read(item: dict[str, Any]) -> Incident:
    result = parse_incident_item(item)
    assert result.is_success
    assert result.data is not None
    return result.data


def _unreadable_fields(logs: Sequence[Mapping[str, Any]]) -> list[str]:
    return [log["field"] for log in logs if log["event"] == "incident_field_unreadable"]


@pytest.mark.parametrize("stored", [0, 4, Decimal(2), Decimal("3.0")])
def test_a_severity_from_0_to_4_reads_as_its_level(stored: object) -> None:
    """DynamoDB numbers arrive as Decimal; an integral one in range is the severity."""
    assert _read(_item(severity=stored)).severity is Severity(int(stored))  # type: ignore[call-overload]


def test_an_absent_severity_is_not_rated_without_a_log() -> None:
    """Absence is the normal unset state, not an unreadable value."""
    with capture_logs() as logs:
        incident = _read(_item())

    assert incident.severity is None
    assert _unreadable_fields(logs) == []


@pytest.mark.parametrize("stored", [5, -1, Decimal("1.5"), "1", True])
def test_an_unreadable_severity_is_not_rated_and_logged(stored: object) -> None:
    """Out of range, fractional, text or a bool: the incident reads with no severity and the field is logged."""
    with capture_logs() as logs:
        incident = _read(_item(severity=stored))

    assert incident.severity is None
    events = [log for log in logs if log["event"] == "incident_field_unreadable"]
    assert [(log["incident_id"], log["field"]) for log in events] == [(INCIDENT_ID, "severity")]
    assert events[0]["value"] == stored


@pytest.mark.parametrize("field", OPTIONAL_TIMES)
def test_an_aware_time_reads_in_its_zone(field: str) -> None:
    """Stored times are ISO-8601 with an offset; any offset is accepted."""
    incident = _read(_item(**{field: "2026-10-15T10:00:00.000000-04:00"}))

    assert getattr(incident, field) == datetime(2026, 10, 15, 10, 0, tzinfo=timezone(timedelta(hours=-4)))
    assert getattr(incident, field) == datetime(2026, 10, 15, 14, 0, tzinfo=UTC)


@pytest.mark.parametrize("field", OPTIONAL_TIMES)
@pytest.mark.parametrize("stored", ["2026-10-15T14:00:00", "not a time", Decimal(1)])
def test_an_unreadable_time_is_not_recorded_and_logged(field: str, stored: object) -> None:
    """A naive, unparseable or non-text time reads as not recorded."""
    with capture_logs() as logs:
        incident = _read(_item(**{field: stored}))

    assert getattr(incident, field) is None
    assert _unreadable_fields(logs) == [field]


def test_a_product_reads_as_given() -> None:
    assert _read(_item(product="GC Notify")).product == "GC Notify"


@pytest.mark.parametrize("stored", ["", "  ", 3])
def test_a_blank_or_non_text_product_is_not_recorded(stored: object) -> None:
    """A blank product is the same as none; a non-text one is also logged."""
    with capture_logs() as logs:
        incident = _read(_item(product=stored))

    assert incident.product is None
    assert _unreadable_fields(logs) == ([] if isinstance(stored, str) else ["product"])


@pytest.mark.parametrize("role", list(IncidentRole))
def test_each_role_reads_by_its_field_name(role: IncidentRole) -> None:
    """Role attributes carry the person's platform id under the role's own name."""
    assert getattr(_read(_item(**{role.value: "U0PERSON"})), role.value) == "U0PERSON"


@pytest.mark.parametrize("role", list(IncidentRole))
def test_a_blank_role_is_not_assigned(role: IncidentRole) -> None:
    assert getattr(_read(_item(**{role.value: " "})), role.value) is None


def test_a_non_text_role_is_not_assigned_and_logged() -> None:
    with capture_logs() as logs:
        incident = _read(_item(incident_commander=Decimal(4)))

    assert incident.incident_commander is None
    assert _unreadable_fields(logs) == ["incident_commander"]
