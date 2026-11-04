"""Behavior tests for the incident legacy upgrade's guarded writes.

Each item is written by one update guarded on record_version absent and on every
attribute the bridge read, at its read value. A concurrent writer is simulated
by an in-memory store that edits the item just before the upgrade's update: the
guard must then fail, the item stay untouched and the report count guard_lost.
"""

from decimal import Decimal
from typing import Any

import pytest

from contracts.records import RemoveAttribute, SetAttribute
from tests.factories.legacy_upgrade import TABLE, legacy_item, legacy_upgrade, records_with

pytestmark = pytest.mark.unit

GUARDED_SCALARS = (
    "status",
    "name",
    "user_id",
    "created_at",
    "security_incident",
    "channel_id",
    "report_url",
    "meet_url",
    "severity",
    "detection_time",
    "start_impact_time",
    "end_impact_time",
    "incident_commander",
    "operations_lead",
)


def _edited_before_update(item: dict[str, Any], attribute: str, value: Any) -> tuple[Any, Any]:
    records = records_with(item)

    def concurrent_edit(key: dict[str, Any]) -> None:
        records.before_update = None
        change = RemoveAttribute(attribute) if value is None else SetAttribute(attribute, value)
        assert records.update(TABLE, key, [change]).is_success

    records.before_update = concurrent_edit
    report = legacy_upgrade(records).run(apply=True)
    return report, records


@pytest.mark.parametrize("attribute", GUARDED_SCALARS)
def test_an_edit_of_any_guarded_attribute_since_the_read_is_guard_lost(attribute: str) -> None:
    item = legacy_item("inc-1")
    report, records = _edited_before_update(item, attribute, "edited")

    stored = records.get(TABLE, {"id": "inc-1"}).data
    assert (report.outcome, report.upgraded, report.guard_lost, report.pending) == ("succeeded", 0, 1, 1)
    assert "record_version" not in stored
    assert stored[attribute] == "edited"


def test_an_end_state_writer_stamping_the_marker_since_the_read_is_guard_lost() -> None:
    report, records = _edited_before_update(legacy_item("inc-1"), "record_version", 1)

    assert (report.upgraded, report.guard_lost) == (0, 1)
    assert "title" not in records.get(TABLE, {"id": "inc-1"}).data


def test_a_removed_attribute_since_the_read_is_guard_lost() -> None:
    report, _ = _edited_before_update(legacy_item("inc-1"), "severity", None)

    assert report.guard_lost == 1


def test_an_end_state_attribute_added_since_the_read_is_guard_lost() -> None:
    report, _ = _edited_before_update(legacy_item("inc-1"), "title", "Renamed by a new writer")

    assert report.guard_lost == 1


def test_a_deleted_item_since_the_read_is_guard_lost() -> None:
    records = records_with(legacy_item("inc-1"))

    def concurrent_delete(key: dict[str, Any]) -> None:
        records.before_update = None
        assert records.delete(TABLE, key).is_success

    records.before_update = concurrent_delete

    report = legacy_upgrade(records).run(apply=True)

    assert (report.upgraded, report.guard_lost, report.pending) == (0, 1, 1)
    assert records.get(TABLE, {"id": "inc-1"}).data is None


def test_a_teams_edit_since_the_read_does_not_lose_the_guard() -> None:
    """teams is not read by the bridge, so a folder change does not hold the upgrade back."""
    report, records = _edited_before_update(legacy_item("inc-1"), "teams", ["GC Forms"])

    assert (report.upgraded, report.guard_lost) == (1, 0)
    assert records.get(TABLE, {"id": "inc-1"}).data["teams"] == ["GC Forms"]


def test_an_integral_decimal_read_value_is_guarded_as_an_integer() -> None:
    """DynamoDB returns numbers as Decimal; an integral one guards as int and the item upgrades."""
    records = records_with(legacy_item("inc-1", created_at=Decimal(1760536800), severity=Decimal(3)))

    report = legacy_upgrade(records).run(apply=True)

    stored = records.get(TABLE, {"id": "inc-1"}).data
    assert (report.upgraded, report.guard_lost) == (1, 0)
    assert stored["severity"] == 3
