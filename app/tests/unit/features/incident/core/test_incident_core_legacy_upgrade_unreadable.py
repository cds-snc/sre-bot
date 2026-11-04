"""Behavior tests for legacy items the incident legacy upgrade cannot read.

A required value the bridge cannot match, or a read value the write guard cannot
express, is never guessed: the item is reported (the status with its stored
value, any other field by name only) and the whole run stops before any write.
Optional values the bridge drops are counted with the item and field and never
block apply. The seeded in-memory store counts writes.
"""

from decimal import Decimal

import pytest

from features.incident.core.store import RECORD_VERSION
from tests.factories.legacy_upgrade import TABLE, legacy_item, legacy_upgrade, records_with

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("apply", [True, False])
def test_every_unreadable_item_is_listed_and_nothing_is_written(apply: bool) -> None:
    records = records_with(
        legacy_item("inc-ok"),
        legacy_item("inc-status", status="Resolved"),
        legacy_item("inc-name", name="  "),
        legacy_item("inc-flag", security_incident="yes"),
    )

    report = legacy_upgrade(records).run(apply=apply)

    assert (report.outcome, report.failures) == ("failed", ("unreadable_items",))
    assert report.unmatched_status == (("inc-status", "Resolved"),)
    assert sorted(report.unreadable) == [("inc-flag", "security_incident"), ("inc-name", "name")]
    assert (report.to_upgrade, report.upgraded, report.pending) == (1, 0, 1)
    assert records.writes == []


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("created_at", Decimal("1760536800.5")),
        ("detection_time", ["1760536700"]),
        ("incident_commander", {"id": "U0"}),
        ("severity", 2.0),
        ("title", {"S": "x"}),
    ],
)
def test_a_read_value_the_guard_cannot_express_makes_the_item_unreadable(attribute: str, value: object) -> None:
    records = records_with(legacy_item("inc-1", **{attribute: value}))

    report = legacy_upgrade(records).run(apply=True)

    assert report.unreadable == (("inc-1", attribute),)
    assert (report.outcome, records.writes) == ("failed", [])


def test_drops_are_counted_with_item_and_field_and_do_not_block_apply() -> None:
    records = records_with(legacy_item("inc-1", severity="critical", report_url="https://example.com/r"), legacy_item("inc-2"))

    report = legacy_upgrade(records).run(apply=True)

    assert report.dropped == (("inc-1", "severity"), ("inc-1", "report_url"))
    assert (report.outcome, report.upgraded) == ("succeeded", 2)
    stored = records.get(TABLE, {"id": "inc-1"}).data
    assert stored["record_version"] == RECORD_VERSION
    assert stored["report_url"] == "https://example.com/r"
