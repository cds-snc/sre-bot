"""Behavior tests for rerunning the incident legacy upgrade.

The version marker makes the upgrade idempotent: a second apply over the same
in-memory store finds every item already upgraded and writes nothing, not even
a binding put.
"""

import pytest

from tests.factories.legacy_upgrade import end_state_item, legacy_item, legacy_upgrade, records_with

pytestmark = pytest.mark.unit


def test_a_second_apply_changes_nothing() -> None:
    records = records_with(legacy_item("inc-1"), legacy_item("inc-2", status="Closed"), end_state_item("inc-3"))
    legacy_upgrade(records).run(apply=True)
    records.writes.clear()

    report = legacy_upgrade(records).run(apply=True)

    assert (report.scanned, report.already_upgraded, report.to_upgrade, report.upgraded, report.pending) == (3, 3, 0, 0, 0)
    assert records.writes == []
