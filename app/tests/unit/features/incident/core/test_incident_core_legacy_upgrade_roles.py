"""Behavior tests for the incident legacy upgrade's roles step.

The runner reads a roleless item's legacy roles from its report's Drive
properties through the in-memory legacy roles reader (seeded per report, or
failing every read with one result), over the counting in-memory record store
of the legacy upgrade factory. Assertions are on the reports read, the report
counts and the stored roles, which is what the step promises: map once, drop
what cannot be read, keep what may come back pending, and never touch an item
whose record holds a role.
"""

from typing import Any

import pytest

from contracts.operations import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import SetAttribute
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.adapters.in_memory import InMemoryLegacyRolesReader
from features.incident.core.adapters.incident_items import RECORD_VERSION
from features.incident.core.domain import ReportReference
from tests.factories.legacy_upgrade import (
    GOOGLE_TENANT,
    REPORT_URL,
    TABLE,
    end_state_item,
    legacy_item,
    legacy_upgrade,
    records_with,
)

pytestmark = pytest.mark.unit

REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="doc123", url=REPORT_URL)
ROLES = {IncidentRole.INCIDENT_COMMANDER: "U0IC", IncidentRole.OPERATIONS_LEAD: "U0OL"}
NO_ROLES: dict[str, Any] = {"incident_commander": None, "operations_lead": None}


def _seeded(roles: dict[IncidentRole, str] = ROLES) -> InMemoryLegacyRolesReader:
    reader = InMemoryLegacyRolesReader()
    reader.seed(REPORT, roles)
    return reader


def _roleless() -> tuple[dict[str, Any], ...]:
    return (
        legacy_item("inc-legacy", **NO_ROLES),
        end_state_item("inc-v1", **NO_ROLES),
        end_state_item("inc-v2", version=RECORD_VERSION, **NO_ROLES),
    )


def _stored_roles(records: Any, incident_id: str) -> tuple[object, object]:
    stored = records.get(TABLE, {"id": incident_id}).data
    assert stored is not None
    return stored.get("incident_commander"), stored.get("operations_lead")


def test_a_dry_run_reads_every_roleless_item_and_writes_nothing() -> None:
    records = records_with(*_roleless())
    reader = _seeded()

    report = legacy_upgrade(records, roles=reader).run(apply=False)

    assert reader.reads == [REPORT, REPORT, REPORT]
    assert (report.roles_to_map, report.roles_mapped, report.roles_none, report.pending) == (3, 0, 0, 3)
    assert (report.to_upgrade, report.already_upgraded, report.outcome) == (2, 1, "succeeded")
    assert records.writes == []


def test_an_apply_writes_the_roles_on_legacy_end_state_and_current_items() -> None:
    records = records_with(*_roleless())

    report = legacy_upgrade(records, roles=_seeded()).run(apply=True)

    assert [_stored_roles(records, incident_id) for incident_id in ("inc-legacy", "inc-v1", "inc-v2")] == [("U0IC", "U0OL")] * 3
    assert (report.upgraded, report.marker_raised, report.roles_mapped, report.pending) == (1, 1, 3, 0)
    assert report.binding_skipped == 0
    assert records.writes.count("update") == 3


def test_a_report_with_no_roles_is_counted_and_never_written() -> None:
    records = records_with(end_state_item("inc-v2", version=RECORD_VERSION, **NO_ROLES))

    report = legacy_upgrade(records, roles=_seeded({})).run(apply=True)

    assert (report.roles_to_map, report.roles_none, report.pending, report.dropped) == (0, 1, 0, ())
    assert records.writes == []


@pytest.mark.parametrize("status", [OperationStatus.NOT_FOUND, OperationStatus.PERMANENT_ERROR])
def test_a_missing_or_unreadable_report_is_dropped_and_the_run_succeeds(status: OperationStatus) -> None:
    records = records_with(legacy_item("inc-1", **NO_ROLES), end_state_item("inc-v2", version=RECORD_VERSION, **NO_ROLES))
    reader = InMemoryLegacyRolesReader(fail_with=OperationResult.error(status, "unreadable"))

    report = legacy_upgrade(records, roles=reader).run(apply=True)

    assert (report.outcome, report.upgraded, report.pending) == ("succeeded", 1, 0)
    assert report.dropped == (("inc-1", "roles"), ("inc-v2", "roles"))
    assert _stored_roles(records, "inc-1") == (None, None)


def test_an_item_without_a_google_report_is_dropped_without_a_read() -> None:
    records = records_with(end_state_item("inc-v2", version=RECORD_VERSION, **NO_ROLES, report=None))
    reader = _seeded()

    report = legacy_upgrade(records, roles=reader).run(apply=True)

    assert (reader.reads, report.dropped, report.outcome) == ([], (("inc-v2", "roles"),), "succeeded")


@pytest.mark.parametrize("status", [OperationStatus.TRANSIENT_ERROR, OperationStatus.UNAUTHORIZED])
def test_a_read_that_may_succeed_later_is_pending_and_the_shape_still_upgrades(status: OperationStatus) -> None:
    records = records_with(legacy_item("inc-1", **NO_ROLES), end_state_item("inc-v2", version=RECORD_VERSION, **NO_ROLES))
    reader = InMemoryLegacyRolesReader(fail_with=OperationResult.error(status, "later"))

    report = legacy_upgrade(records, roles=reader).run(apply=True)

    assert report.roles_unread == (("inc-1", status.value), ("inc-v2", status.value))
    assert (report.outcome, report.upgraded, report.pending, report.dropped) == ("succeeded", 1, 2, ())
    assert records.writes == ["put_if_not_exists", "update"]


def test_an_unknown_read_failure_propagates_before_any_write() -> None:
    records = records_with(legacy_item("inc-a"), legacy_item("inc-b", **NO_ROLES))

    def refuse(report: ReportReference) -> OperationResult[Any]:
        raise RuntimeError("credentials refused")

    with pytest.raises(RuntimeError):
        legacy_upgrade(records, read_roles=refuse).run(apply=True)

    assert records.writes == []


def test_a_concurrent_role_write_wins_over_the_mapped_roles() -> None:
    records = records_with(end_state_item("inc-v2", version=RECORD_VERSION, **NO_ROLES))

    def concurrent_set_roles(key: dict[str, Any]) -> None:
        records.before_update = None
        assert records.update(TABLE, key, [SetAttribute("incident_commander", "U0LIVE")]).is_success

    records.before_update = concurrent_set_roles
    report = legacy_upgrade(records, roles=_seeded()).run(apply=True)

    assert (report.guard_lost, report.roles_mapped, report.pending) == (1, 0, 1)
    assert _stored_roles(records, "inc-v2") == ("U0LIVE", None)


def test_a_rerun_reads_nothing_once_mapped_and_writes_nothing_for_dropped_items() -> None:
    records = records_with(*_roleless(), end_state_item("inc-lost", version=RECORD_VERSION, **NO_ROLES, report=None))
    legacy_upgrade(records, roles=_seeded()).run(apply=True)
    records.writes.clear()
    reader = _seeded()

    report = legacy_upgrade(records, roles=reader).run(apply=True)

    assert (reader.reads, records.writes) == ([], [])
    assert (report.roles_to_map, report.pending, report.dropped) == (0, 0, (("inc-lost", "roles"),))


def test_an_item_holding_a_role_is_never_read() -> None:
    records = records_with(legacy_item("inc-1"), end_state_item("inc-v2", version=RECORD_VERSION, policy_lead="U0P"))
    reader = _seeded()

    legacy_upgrade(records, roles=reader).run(apply=False)

    assert reader.reads == []


def test_a_blocked_item_is_not_read_and_the_blocked_run_writes_nothing() -> None:
    records = records_with(legacy_item("inc-bad", **NO_ROLES, status="Bogus"), legacy_item("inc-ok", **NO_ROLES))
    reader = _seeded()

    report = legacy_upgrade(records, roles=reader).run(apply=True)

    assert (reader.reads, report.outcome, report.roles_to_map) == ([REPORT], "failed", 1)
    assert records.writes == []
