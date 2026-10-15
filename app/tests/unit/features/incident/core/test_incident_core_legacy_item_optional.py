"""Behavior tests for the legacy item bridge: optional values.

An optional legacy value that is "Unknown", blank or absent is not recorded.
One that cannot be matched is dropped and logged with the incident id and the
legacy attribute, and the incident stays readable. Results are read back with
the end-state parser; logs are captured with structlog's capture_logs.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import Severity
from features.incident.core.adapters.incident_items import parse_incident_item
from features.incident.core.adapters.legacy_items import UpgradedItem, upgrade_legacy_item
from features.incident.core.domain import Incident

pytestmark = pytest.mark.unit

INCIDENT_ID = "inc-legacy"
TENANTS = {WorkplaceSystem.SLACK: "T0SLACK", WorkplaceSystem.GOOGLE: "C0GOOGLE"}


def _legacy(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": INCIDENT_ID,
        "name": "Notify emails delayed",
        "user_id": "U0DECLARER",
        "status": "Open",
        "created_at": "1760536800",
    }
    item.update(overrides)
    return item


def _upgraded(item: dict[str, Any]) -> dict[str, Any]:
    upgraded = upgrade_legacy_item(item, TENANTS)
    assert isinstance(upgraded, UpgradedItem)
    return dict(upgraded.item)


def _read(item: dict[str, Any]) -> Incident:
    parsed = parse_incident_item(_upgraded(item))
    assert parsed.data is not None
    return parsed.data


def _dropped(logs: list[dict[str, Any]]) -> list[tuple[object, str]]:
    return [(log["incident_id"], log["field"]) for log in logs if log["event"] == "incident_legacy_field_dropped"]


def test_a_minimal_legacy_item_records_nothing_optional() -> None:
    incident = _read(_legacy())

    assert incident.product is None
    assert incident.severity is None
    assert (incident.detected_at, incident.impact_started_at, incident.impact_ended_at) == (None, None, None)
    assert (incident.incident_commander, incident.operations_lead) == (None, None)
    assert (incident.conversation, incident.report, incident.video_call) == (None, None, None)


def test_the_first_team_is_the_product() -> None:
    assert _read(_legacy(teams=["GC Notify", "GC Forms"])).product == "GC Notify"


@pytest.mark.parametrize("teams", [["Unknown"], ["unknown "], [""], ["  "], []])
def test_an_unknown_or_blank_team_is_no_product(teams: list[str]) -> None:
    with capture_logs() as logs:
        incident = _read(_legacy(teams=teams))

    assert incident.product is None
    assert _dropped(logs) == []


def test_teams_that_are_not_a_list_are_dropped_and_logged() -> None:
    with capture_logs() as logs:
        incident = _read(_legacy(teams="GC Notify"))

    assert incident.product is None
    assert _dropped(logs) == [(INCIDENT_ID, "teams")]


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("sev-0", Severity.SEV0),
        ("sev-1", Severity.SEV1),
        ("SEV-2", Severity.SEV2),
        (" sev - 3 ", Severity.SEV3),
        ("Sev-4", Severity.SEV4),
    ],
)
def test_a_severity_matches_ignoring_case_and_spaces(stored: str, expected: Severity) -> None:
    assert _read(_legacy(severity=stored)).severity is expected


@pytest.mark.parametrize("stored", ["none", "None", "", "  "])
def test_a_none_or_blank_severity_is_unset_without_a_log(stored: str) -> None:
    with capture_logs() as logs:
        incident = _read(_legacy(severity=stored))

    assert incident.severity is None
    assert _dropped(logs) == []


@pytest.mark.parametrize("stored", ["critical", "sev-5", "sev1x"])
def test_an_unmatched_severity_is_unset_and_logged_with_the_value(stored: str) -> None:
    with capture_logs() as logs:
        incident = _read(_legacy(severity=stored))

    assert incident.severity is None
    dropped = [log for log in logs if log["event"] == "incident_legacy_field_dropped"]
    assert [(log["incident_id"], log["field"], log["value"]) for log in dropped] == [(INCIDENT_ID, "severity", stored)]


def test_the_three_times_map_to_their_record_fields() -> None:
    incident = _read(
        _legacy(detection_time="1760536700", start_impact_time="1760536600", end_impact_time="2025-10-15T15:00:00+00:00")
    )

    assert incident.detected_at == datetime(2025, 10, 15, 13, 58, 20, tzinfo=UTC)
    assert incident.impact_started_at == datetime(2025, 10, 15, 13, 56, 40, tzinfo=UTC)
    assert incident.impact_ended_at == datetime(2025, 10, 15, 15, 0, tzinfo=UTC)


def test_times_are_written_in_the_stored_time_form() -> None:
    upgraded = _upgraded(_legacy(detection_time="1760536700.5"))

    assert upgraded["detected_at"] == "2025-10-15T13:58:20.500000+00:00"


@pytest.mark.parametrize("stored", ["Unknown", "unknown", "", "  "])
def test_an_unknown_or_blank_time_is_not_recorded(stored: str) -> None:
    with capture_logs() as logs:
        upgraded = _upgraded(_legacy(detection_time=stored, start_impact_time=stored, end_impact_time=stored))

    assert {"detected_at", "impact_started_at", "impact_ended_at"}.isdisjoint(upgraded)
    assert _dropped(logs) == []


def test_an_unreadable_time_is_dropped_and_logged() -> None:
    """A naive time is not assumed to be UTC; the optional field is dropped instead."""
    with capture_logs() as logs:
        incident = _read(_legacy(start_impact_time="2025-10-15 14:00", end_impact_time="soon"))

    assert (incident.impact_started_at, incident.impact_ended_at) == (None, None)
    assert _dropped(logs) == [(INCIDENT_ID, "start_impact_time"), (INCIDENT_ID, "end_impact_time")]


def test_the_two_legacy_roles_are_assigned() -> None:
    incident = _read(_legacy(incident_commander="U0COMMANDER", operations_lead="U0OPS"))

    assert (incident.incident_commander, incident.operations_lead) == ("U0COMMANDER", "U0OPS")


@pytest.mark.parametrize("stored", ["", "  "])
def test_a_blank_role_is_not_assigned(stored: str) -> None:
    assert _read(_legacy(incident_commander=stored)).incident_commander is None


@pytest.mark.parametrize("field", ["retrospective_url", "channel_name", "environment", "logs"])
def test_attributes_without_a_record_field_are_skipped(field: str) -> None:
    upgraded = _upgraded(_legacy(**{field: "https://docs.google.com/document/d/retro/edit"}))

    assert field not in upgraded
