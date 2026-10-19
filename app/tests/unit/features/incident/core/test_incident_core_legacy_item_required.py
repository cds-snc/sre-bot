"""Behavior tests for the legacy item bridge: required values and the never-raise rule.

Items are shaped as the legacy writers stored them (declare, the field update
modal and the sheet import). The upgraded item is checked by reading it with
the end-state parser, the only reader it feeds, so the tests assert the record
a legacy item becomes. A required value that cannot be matched is an
UnreadableLegacyItem naming the incident id, the legacy attribute and the
stored value; nothing is guessed and nothing raises.
"""

import ast
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters import legacy_items
from features.incident.core.adapters.incident_items import parse_incident_item
from features.incident.core.adapters.legacy_items import UnreadableLegacyItem, UpgradedItem, upgrade_legacy_item
from features.incident.core.domain import Incident

pytestmark = pytest.mark.unit

INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"
TENANTS = {WorkplaceSystem.SLACK: "T0SLACK", WorkplaceSystem.GOOGLE: "C0GOOGLE"}
DECLARED_EPOCH = "1760536800.123456"  # 2025-10-15T14:00:00.123456Z
DECLARED_AT = datetime(2025, 10, 15, 14, 0, 0, 123456, tzinfo=UTC)


def _legacy(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": INCIDENT_ID,
        "channel_id": "C0INCIDENT",
        "channel_name": "incident-2025-10-15-notify",
        "name": "Notify emails delayed",
        "user_id": "U0DECLARER",
        "teams": ["GC Notify"],
        "report_url": "https://docs.google.com/document/d/1AbC-dEf_123/edit",
        "status": "Open",
        "created_at": DECLARED_EPOCH,
        "start_impact_time": "Unknown",
        "end_impact_time": "Unknown",
        "detection_time": "Unknown",
        "environment": "prod",
        "logs": [],
        "meet_url": "https://meet.google.com/abc-defg-hij",
    }
    item.update(overrides)
    return {key: value for key, value in item.items() if value is not None}


def _read(item: dict[str, Any]) -> Incident:
    upgraded = upgrade_legacy_item(item, TENANTS)
    assert isinstance(upgraded, UpgradedItem)
    parsed = parse_incident_item(upgraded.item)
    assert parsed.data is not None, parsed
    return parsed.data


def _unreadable(item: dict[str, Any]) -> UnreadableLegacyItem:
    upgraded = upgrade_legacy_item(item, TENANTS)
    assert isinstance(upgraded, UnreadableLegacyItem)
    return upgraded


def test_a_declared_legacy_item_reads_as_the_incident() -> None:
    incident = _read(_legacy())

    assert (incident.id, incident.title, incident.declared_by) == (INCIDENT_ID, "Notify emails delayed", "U0DECLARER")
    assert incident.status is IncidentStatus.OPEN
    assert incident.declared_at == DECLARED_AT
    assert incident.security_incident is False


def test_the_upgraded_item_carries_no_version_or_open_index_attributes() -> None:
    """The writers and the upgrade job stamp those; the bridge only maps what the legacy item holds."""
    upgraded = upgrade_legacy_item(_legacy(), TENANTS)

    assert isinstance(upgraded, UpgradedItem)
    assert {"record_version", "open_bucket", "opened_at", "channel_id"}.isdisjoint(upgraded.item)


def test_declared_at_is_written_in_the_stored_time_form() -> None:
    upgraded = upgrade_legacy_item(_legacy(), TENANTS)

    assert isinstance(upgraded, UpgradedItem)
    assert upgraded.item["declared_at"] == "2025-10-15T14:00:00.123456+00:00"


@pytest.mark.parametrize(
    "created_at",
    [
        DECLARED_EPOCH,
        Decimal(DECLARED_EPOCH),
        "2025-10-15T14:00:00.123456+00:00",
        "2025-10-15T14:00:00.123456Z",
        "2025-10-15T10:00:00.123456-04:00",
    ],
)
def test_created_at_reads_as_epoch_seconds_or_iso_with_an_offset(created_at: object) -> None:
    assert _read(_legacy(created_at=created_at)).declared_at == DECLARED_AT


def test_a_whole_second_epoch_reads_exactly() -> None:
    assert _read(_legacy(created_at="1760536800")).declared_at == datetime(2025, 10, 15, 14, 0, tzinfo=UTC)


@pytest.mark.parametrize("stored", ["closed", "CLOSED", " Closed ", "Closed"])
def test_a_status_matches_ignoring_case_and_surrounding_spaces(stored: str) -> None:
    """Production holds lowercase closed and reviewed; the stored form is the canonical value."""
    upgraded = upgrade_legacy_item(_legacy(status=stored), TENANTS)

    assert isinstance(upgraded, UpgradedItem)
    assert upgraded.item["status"] == "Closed"


@pytest.mark.parametrize("stored", ["reviewed", "in progress", "Ready to be Reviewed", "open"])
def test_every_production_status_form_reads(stored: str) -> None:
    assert _read(_legacy(status=stored)).status.casefold() == stored.casefold()


@pytest.mark.parametrize(("security_incident", "expected"), [(None, False), (False, False), (True, True)])
def test_a_missing_security_flag_reads_as_false(security_incident: bool | None, expected: bool) -> None:
    assert _read(_legacy(security_incident=security_incident)).security_incident is expected


@pytest.mark.parametrize(
    ("overrides", "field", "value"),
    [
        ({"status": "Done"}, "status", "Done"),
        ({"status": None}, "status", None),
        ({"status": ""}, "status", ""),
        ({"name": None}, "name", None),
        ({"name": "  "}, "name", "  "),
        ({"user_id": ""}, "user_id", ""),
        ({"user_id": Decimal(5)}, "user_id", Decimal(5)),
        ({"created_at": None}, "created_at", None),
        ({"created_at": "Unknown"}, "created_at", "Unknown"),
        ({"created_at": "2025-10-15 14:00:00.123456"}, "created_at", "2025-10-15 14:00:00.123456"),
        ({"created_at": "2025-10-15"}, "created_at", "2025-10-15"),
        ({"created_at": "NaN"}, "created_at", "NaN"),
        ({"created_at": "Infinity"}, "created_at", "Infinity"),
        ({"created_at": "1e30"}, "created_at", "1e30"),
        ({"created_at": "1e999999999"}, "created_at", "1e999999999"),
        ({"created_at": "sNaN"}, "created_at", "sNaN"),
        ({"created_at": True}, "created_at", True),
        ({"security_incident": "yes"}, "security_incident", "yes"),
        ({"id": ""}, "id", ""),
        ({"id": None}, "id", None),
    ],
)
def test_an_unmatched_required_value_is_unreadable_with_its_field_and_value(
    overrides: dict[str, Any], field: str, value: object
) -> None:
    """A naive or date-only created_at is never assumed to be UTC."""
    item = _legacy(**overrides)
    for key, stored in overrides.items():
        if stored is None:
            item.pop(key, None)

    unreadable = _unreadable(item)

    assert (unreadable.field, unreadable.value) == (field, value)
    assert unreadable.incident_id == item.get("id")


@pytest.mark.parametrize(
    "overrides",
    [
        {"teams": "GC Notify"},
        {"teams": [Decimal(1)]},
        {"severity": Decimal(2)},
        {"severity": ["sev-1"]},
        {"report_url": Decimal(3)},
        {"meet_url": {"url": "x"}},
        {"channel_id": ["C0"]},
        {"incident_commander": Decimal(4)},
        {"detection_time": {"S": "1"}},
        {"name": Decimal(1)},
        {"created_at": Decimal("NaN")},
        {"created_at": Decimal("-1e30")},
        {"status": Decimal(1)},
    ],
)
def test_any_stored_value_type_returns_a_result_without_raising(overrides: dict[str, Any]) -> None:
    upgraded = upgrade_legacy_item(_legacy(**overrides), TENANTS)

    assert isinstance(upgraded, UpgradedItem | UnreadableLegacyItem)


def test_the_input_item_is_left_unchanged_and_the_result_repeats() -> None:
    item = _legacy(status="closed", severity="SEV-1")
    snapshot = dict(item)

    first = upgrade_legacy_item(item, TENANTS)
    second = upgrade_legacy_item(item, TENANTS)

    assert item == snapshot
    assert first == second


def test_the_bridge_imports_no_settings() -> None:
    """The tenants come from the caller; the bridge reads no configuration of its own."""
    tree = ast.parse(Path(legacy_items.__file__).read_text())
    imported = [
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    ]

    assert [name for name in imported if name and ("settings" in name or "configuration" in name)] == []


def test_a_time_with_an_offset_is_kept_as_the_same_instant() -> None:
    created_at = datetime(2025, 10, 15, 11, 30, tzinfo=timezone(timedelta(hours=-2, minutes=-30)))

    assert _read(_legacy(created_at=created_at.isoformat())).declared_at == created_at
