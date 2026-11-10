"""Behavior tests for the incident legacy upgrade's binding step.

Items are seeded in an in-memory record store with a bindings table beside it.
Per item the job puts the binding first and then makes one guarded update with
the marker last; stores that fail or act as a concurrent writer between the two
steps show that every interruption converges on a rerun. The stored binding is
read back through the binding item parser, and one test finds the incident
through the real store's conversation lookup.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest

from contracts.operations import OperationResult
from contracts.records import ExpectedValue, RecordChange, RecordTable, SetAttribute
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.binding_items import binding_item, binding_key, parse_binding_item
from features.incident.core.adapters.incident_items import RECORD_VERSION
from features.incident.core.domain import BindingKind, ConversationReference, IncidentBinding
from tests.factories.incident import SLACK_TENANT, record_incident_store
from tests.factories.legacy_upgrade import (
    BINDINGS,
    TABLE,
    TENANTS,
    InterceptingRecordStore,
    end_state_item,
    legacy_item,
    legacy_upgrade,
    records_with,
)

pytestmark = pytest.mark.unit

SLACK = WorkplaceSystem.SLACK


def _stored_binding(records: InterceptingRecordStore, incident_id: str, vendor_id: str) -> IncidentBinding | None:
    key = binding_key(BindingKind.CHAT_CONVERSATION, SLACK, SLACK_TENANT, vendor_id)
    result = records.get(BINDINGS, {"incident_id": incident_id, "binding_key": key})
    return None if result.data is None else parse_binding_item(result.data)


def _item(records: InterceptingRecordStore, incident_id: str) -> dict[str, Any]:
    data = records.get(TABLE, {"id": incident_id}).data
    assert data is not None
    return dict(data)


class _FailingStore(InterceptingRecordStore):
    """Counting store whose binding puts or item updates fail with a permanent error."""

    def __init__(self, *, fail_put: bool = False, fail_update: bool = False) -> None:
        super().__init__()
        self.fail_put = fail_put
        self.fail_update = fail_update
        self.update_attempts = 0

    def put_if_not_exists(self, table: RecordTable, item: dict[str, Any]) -> OperationResult:
        if self.fail_put and table.name == BINDINGS.name:
            return OperationResult.permanent_error("put failed", "STORE_FAILED")
        return super().put_if_not_exists(table, item)

    def update(
        self,
        table: RecordTable,
        key: dict[str, Any],
        changes: Sequence[RecordChange],
        *,
        expected: Mapping[str, ExpectedValue] | None = None,
    ) -> OperationResult:
        self.update_attempts += 1
        if self.fail_update:
            return OperationResult.permanent_error("update failed", "STORE_FAILED")
        return super().update(table, key, changes, expected=expected)


def _seed(records: InterceptingRecordStore, *items: dict[str, Any]) -> None:
    for item in items:
        assert records.put(TABLE, item).is_success
    records.writes.clear()


def test_one_pass_gives_the_item_its_binding_and_the_marker() -> None:
    records = records_with(legacy_item("inc-1"))

    report = legacy_upgrade(records).run(apply=True)

    binding = _stored_binding(records, "inc-1", "C0INC-1")
    assert (report.outcome, report.upgraded, report.bindings_put, report.pending) == ("succeeded", 1, 1, 0)
    assert binding is not None and (binding.primary, binding.bound_by) == (True, "U0DECLARER")
    assert _item(records, "inc-1")["record_version"] == RECORD_VERSION
    stored = records.get(
        BINDINGS, {"incident_id": "inc-1", "binding_key": binding_key(binding.kind, SLACK, SLACK_TENANT, "C0INC-1")}
    )
    assert stored.data is not None and stored.data["conversation_id"] == "C0INC-1"


def test_the_incident_is_found_by_its_conversation_after_the_upgrade() -> None:
    records = records_with(legacy_item("inc-1"))
    legacy_upgrade(records).run(apply=True)

    found = record_incident_store(records, table=TABLE, tenants=TENANTS, bindings=BINDINGS).find_by_conversation(
        ConversationReference(system=SLACK, tenant=SLACK_TENANT, vendor_id="C0INC-1")
    )

    assert found.data is not None and found.data.id == "inc-1"


def test_two_incidents_get_two_bindings_keyed_by_their_own_ids() -> None:
    records = records_with(legacy_item("inc-1"), legacy_item("inc-2"))

    report = legacy_upgrade(records).run(apply=True)

    first, second = _stored_binding(records, "inc-1", "C0INC-1"), _stored_binding(records, "inc-2", "C0INC-2")
    assert report.bindings_put == 2
    assert first is not None and second is not None and (first.incident_id, second.incident_id) == ("inc-1", "inc-2")


def test_a_rerun_changes_nothing_including_binding_puts() -> None:
    records = records_with(legacy_item("inc-1"), end_state_item("inc-2"))
    legacy_upgrade(records).run(apply=True)
    records.writes.clear()

    report = legacy_upgrade(records).run(apply=True)

    assert records.writes == []
    assert (report.already_upgraded, report.upgraded, report.marker_raised, report.bindings_put, report.bindings_existing) == (
        2,
        0,
        0,
        0,
        0,
    )


def test_a_crash_between_the_binding_put_and_the_update_converges_on_the_rerun() -> None:
    records = records_with(legacy_item("inc-1"))

    def crash(_key: dict[str, Any]) -> None:
        raise RuntimeError("process died")

    records.before_update = crash
    with pytest.raises(RuntimeError):
        legacy_upgrade(records).run(apply=True)
    assert _stored_binding(records, "inc-1", "C0INC-1") is not None
    assert "record_version" not in _item(records, "inc-1")
    records.before_update = None

    report = legacy_upgrade(records).run(apply=True)

    assert (report.outcome, report.upgraded, report.bindings_existing, report.bindings_put, report.pending) == (
        "succeeded",
        1,
        1,
        0,
        0,
    )
    assert _item(records, "inc-1")["record_version"] == RECORD_VERSION


def test_a_failed_update_after_the_put_is_a_write_failure_and_the_rerun_converges() -> None:
    records = _FailingStore(fail_update=True)
    _seed(records, legacy_item("inc-1"))

    failed = legacy_upgrade(records).run(apply=True)
    records.fail_update = False
    rerun = legacy_upgrade(records).run(apply=True)

    assert (failed.failures, failed.bindings_put, failed.upgraded) == (("write_failed",), 1, 0)
    assert (rerun.outcome, rerun.bindings_existing, rerun.upgraded) == ("succeeded", 1, 1)


def test_a_guard_lost_after_the_put_leaves_the_binding_and_the_item_pending_until_the_rerun() -> None:
    records = records_with(legacy_item("inc-1"))

    def concurrent_edit(key: dict[str, Any]) -> None:
        records.before_update = None
        assert records.update(TABLE, key, [SetAttribute("severity", "sev-1")]).is_success

    records.before_update = concurrent_edit
    lost = legacy_upgrade(records).run(apply=True)
    rerun = legacy_upgrade(records).run(apply=True)

    assert (lost.guard_lost, lost.pending, lost.bindings_put) == (1, 1, 1)
    assert (rerun.upgraded, rerun.bindings_existing, rerun.pending) == (1, 1, 0)


def test_a_failed_binding_put_stops_before_any_update_and_leaves_the_item_untouched() -> None:
    records = _FailingStore(fail_put=True)
    _seed(records, legacy_item("inc-1"))

    report = legacy_upgrade(records).run(apply=True)

    assert (report.failures, report.upgraded, report.bindings_put) == (("write_failed",), 0, 0)
    assert records.update_attempts == 0
    assert "record_version" not in _item(records, "inc-1")


@pytest.mark.parametrize("apply", [True, False])
def test_an_open_item_without_a_conversation_fails_the_run_before_any_write(apply: bool) -> None:
    records = records_with(
        legacy_item("inc-ok"), legacy_item("inc-open", channel_id=None), end_state_item("inc-v1", conversation=None)
    )

    report = legacy_upgrade(records).run(apply=apply)

    assert report.outcome == "failed"
    assert "open_items_without_conversation" in report.failures
    assert sorted(str(incident_id) for incident_id in report.unbound) == ["inc-open", "inc-v1"]
    assert records.writes == []


def test_a_closed_item_without_a_conversation_is_only_raised() -> None:
    records = records_with(legacy_item("inc-1", status="Closed", channel_id=None))

    report = legacy_upgrade(records).run(apply=True)

    assert (report.outcome, report.upgraded, report.binding_skipped, report.bindings_put) == ("succeeded", 1, 1, 0)
    assert _item(records, "inc-1")["record_version"] == RECORD_VERSION
    assert records.writes == ["update"]


def test_a_closed_item_with_a_conversation_keeps_its_binding() -> None:
    records = records_with(legacy_item("inc-1", status="Closed"))

    report = legacy_upgrade(records).run(apply=True)

    assert (report.bindings_put, report.binding_skipped) == (1, 0)
    assert _stored_binding(records, "inc-1", "C0INC-1") is not None


def test_a_version_one_item_gets_its_binding_and_only_the_marker_changes() -> None:
    before = end_state_item("inc-1")
    records = records_with(before)

    report = legacy_upgrade(records).run(apply=True)

    after = _item(records, "inc-1")
    assert (report.outcome, report.marker_raised, report.upgraded, report.bindings_put, report.pending) == (
        "succeeded",
        1,
        0,
        1,
        0,
    )
    assert after == {**before, "record_version": RECORD_VERSION}
    assert _stored_binding(records, "inc-1", "C0INC-1") is not None


def test_a_version_one_item_edited_before_the_raise_is_guard_lost() -> None:
    records = records_with(end_state_item("inc-1"))

    def concurrent_edit(key: dict[str, Any]) -> None:
        records.before_update = None
        assert records.update(TABLE, key, [SetAttribute("status", "In Progress")]).is_success

    records.before_update = concurrent_edit
    report = legacy_upgrade(records).run(apply=True)

    assert (report.marker_raised, report.guard_lost, report.pending) == (0, 1, 1)
    assert _item(records, "inc-1")["record_version"] == 1


def test_an_existing_binding_is_never_overwritten_and_the_item_is_still_raised() -> None:
    records = records_with(legacy_item("inc-1"))
    archived = IncidentBinding(
        incident_id="inc-1",
        kind=BindingKind.CHAT_CONVERSATION,
        system=SLACK,
        tenant=SLACK_TENANT,
        vendor_id="C0INC-1",
        primary=False,
        bound_by="U0OTHER",
        bound_at=datetime(2026, 1, 1, tzinfo=UTC),
        archived_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    assert records.put(BINDINGS, binding_item(archived)).is_success

    report = legacy_upgrade(records).run(apply=True)

    assert (report.bindings_existing, report.bindings_put, report.upgraded) == (1, 0, 1)
    assert _stored_binding(records, "inc-1", "C0INC-1") == archived


def test_a_dry_run_counts_the_plan_and_writes_nothing() -> None:
    records = records_with(legacy_item("inc-1"), end_state_item("inc-2"), legacy_item("inc-3", status="Closed", channel_id=None))

    report = legacy_upgrade(records).run(apply=False)

    assert records.writes == []
    assert (report.outcome, report.to_upgrade, report.binding_skipped, report.bindings_put, report.upgraded) == (
        "succeeded",
        3,
        1,
        0,
        0,
    )
    assert report.pending == 3


def test_a_mixed_table_is_counted_right_in_one_run() -> None:
    records = records_with(
        legacy_item("inc-legacy"),
        end_state_item("inc-v1"),
        end_state_item("inc-v2", version=RECORD_VERSION),
        legacy_item("inc-closed", status="Closed", channel_id=None),
    )

    report = legacy_upgrade(records).run(apply=True)

    assert (report.scanned, report.already_upgraded, report.to_upgrade) == (4, 1, 3)
    assert (report.upgraded, report.marker_raised, report.bindings_put, report.binding_skipped) == (2, 1, 2, 1)
    assert (report.bindings_existing, report.guard_lost, report.pending, report.unbound) == (0, 0, 0, ())
