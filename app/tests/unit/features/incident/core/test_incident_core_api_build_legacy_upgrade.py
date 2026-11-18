"""Behavior tests for build_legacy_upgrade, the incident legacy upgrade builder in core/api.py.

The builder runs over a seeded in-memory record store, the shared
FakeConfiguredSystems and FakeTenantVerifier, and IncidentCoreSettings built
from explicit values. Running the built upgrade shows the table name, the cap
and the tenants it was given: the entry point resolves those services in its
service scope and passes them in. The roles read is a stub function that
records the reports it is given; the seeded legacy items hold their roles, so
only the roleless item of the last test is read.
"""

from typing import Any

import pytest

from contracts.operations import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import IncidentCoreSettings
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.adapters.binding_items import binding_key
from features.incident.core.api import LegacyUpgrade, UpgradeReport, build_legacy_upgrade
from features.incident.core.domain import BindingKind, ReportReference
from features.incident.core.store import bindings_table, incidents_table
from tests.factories.incident import SLACK_TENANT, CountingRecordStore, FakeConfiguredSystems
from tests.factories.legacy_upgrade import TENANTS, legacy_item, verified_slack

pytestmark = pytest.mark.unit

TABLE_NAME = "incidents-under-test"
BINDINGS_NAME = "bindings-under-test"


def _unread(report: ReportReference) -> OperationResult[Any]:
    return OperationResult.error(OperationStatus.TRANSIENT_ERROR, "not read")


def _records(*incident_ids: str) -> CountingRecordStore:
    records = CountingRecordStore()
    for incident_id in incident_ids:
        assert records.put(incidents_table(TABLE_NAME), legacy_item(incident_id)).is_success
    return records


def test_the_built_upgrade_reads_the_configured_table_with_the_configured_cap() -> None:
    settings = IncidentCoreSettings(incidents_table=TABLE_NAME, full_read_max_items=1)

    upgrade = build_legacy_upgrade(
        _records("inc-1", "inc-2"), FakeConfiguredSystems(TENANTS), verified_slack(), settings, read_roles=_unread
    )
    report = upgrade.run(apply=False)

    assert isinstance(upgrade, LegacyUpgrade)
    assert isinstance(report, UpgradeReport)
    assert (report.failures, report.cap) == (("read_limit_exceeded",), 1)


def test_the_built_upgrade_puts_bindings_in_the_configured_bindings_table() -> None:
    records = _records("inc-1")
    settings = IncidentCoreSettings(incidents_table=TABLE_NAME, bindings_table=BINDINGS_NAME)

    report = build_legacy_upgrade(records, FakeConfiguredSystems(TENANTS), verified_slack(), settings, read_roles=_unread).run(
        apply=True
    )

    key = binding_key(BindingKind.CHAT_CONVERSATION, WorkplaceSystem.SLACK, SLACK_TENANT, "C0INC-1")
    stored = records.get(bindings_table(BINDINGS_NAME), {"incident_id": "inc-1", "binding_key": key})
    assert report.bindings_put == 1
    assert stored.data is not None and stored.data["bound_by"] == "U0DECLARER"


def test_the_built_upgrade_stamps_the_configured_slack_tenant() -> None:
    records = _records("inc-1")
    settings = IncidentCoreSettings(incidents_table=TABLE_NAME)

    report = build_legacy_upgrade(records, FakeConfiguredSystems(TENANTS), verified_slack(), settings, read_roles=_unread).run(
        apply=True
    )

    stored = records.get(incidents_table(TABLE_NAME), {"id": "inc-1"}).data
    assert report.upgraded == 1
    assert stored is not None and stored["conversation"]["tenant"] == SLACK_TENANT


def test_the_built_upgrade_reads_a_roleless_item_through_the_given_roles_read() -> None:
    records = CountingRecordStore()
    roleless = legacy_item("inc-1", incident_commander=None, operations_lead=None)
    assert records.put(incidents_table(TABLE_NAME), roleless).is_success
    settings = IncidentCoreSettings(incidents_table=TABLE_NAME)
    reads: list[ReportReference] = []

    def read_roles(report: ReportReference) -> OperationResult[Any]:
        reads.append(report)
        return OperationResult.success({IncidentRole.INCIDENT_COMMANDER: "U0IC"})

    report = build_legacy_upgrade(records, FakeConfiguredSystems(TENANTS), verified_slack(), settings, read_roles=read_roles).run(
        apply=True
    )

    stored = records.get(incidents_table(TABLE_NAME), {"id": "inc-1"}).data
    assert [read.vendor_id for read in reads] == ["doc123"]
    assert report.roles_mapped == 1
    assert stored is not None and stored["incident_commander"] == "U0IC"
