"""Behavior tests for the incident legacy upgrade in dry-run mode.

A dry run reads, classifies and checks the tenant exactly as apply does, reports
the counts, and writes nothing: the seeded in-memory store counts every write.
"""

from decimal import Decimal

import pytest

from tests.factories.legacy_upgrade import legacy_item, legacy_upgrade, records_with

pytestmark = pytest.mark.unit


def test_a_dry_run_reports_the_counts_and_writes_nothing() -> None:
    records = records_with(legacy_item("inc-1"), legacy_item("inc-2"), {**legacy_item("inc-3"), "record_version": Decimal(1)})

    report = legacy_upgrade(records).run(apply=False)

    assert (report.mode, report.outcome) == ("dry_run", "succeeded")
    assert (report.scanned, report.already_upgraded, report.to_upgrade) == (3, 1, 2)
    assert (report.upgraded, report.guard_lost, report.pending) == (0, 0, 2)
    assert records.writes == []
