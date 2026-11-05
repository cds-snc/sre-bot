"""Behavior tests for the incident legacy upgrade's whole-table read.

The upgrade reads the incidents table once, capped by the configured
full_read_max_items. Items are seeded in an in-memory record store that counts
writes; a table past the cap, or a read that fails, ends the run before any
write, and the report names the cap so the operator knows which key to raise.
"""

from typing import Any

import pytest

from contracts.operations import OperationResult
from contracts.records import RecordTable
from tests.factories.legacy_upgrade import InterceptingRecordStore, legacy_item, legacy_upgrade, records_with

pytestmark = pytest.mark.unit


def test_a_table_past_the_cap_fails_naming_the_cap_and_writes_nothing() -> None:
    records = records_with(legacy_item("inc-1"), legacy_item("inc-2"), legacy_item("inc-3"))

    report = legacy_upgrade(records, max_items=2).run(apply=True)

    assert (report.outcome, report.failures, report.cap) == ("failed", ("read_limit_exceeded",), 2)
    assert (report.scanned, report.upgraded, report.pending) == (0, 0, 0)
    assert records.writes == []


def test_a_table_exactly_at_the_cap_is_upgraded() -> None:
    records = records_with(legacy_item("inc-1"), legacy_item("inc-2"))

    report = legacy_upgrade(records, max_items=2).run(apply=True)

    assert (report.outcome, report.scanned, report.upgraded) == ("succeeded", 2, 2)


class _FailingReadStore(InterceptingRecordStore):
    def read_all(self, table: RecordTable, *, max_items: int) -> OperationResult[Any]:
        return OperationResult.transient_error("store unavailable")


def test_a_failed_read_fails_the_run_without_a_write() -> None:
    records = _FailingReadStore()

    report = legacy_upgrade(records).run(apply=True)

    assert (report.outcome, report.failures) == ("failed", ("read_failed",))
    assert records.writes == []
