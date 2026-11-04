"""Behavior tests for build_legacy_upgrade, the incident legacy upgrade builder in core/api.py.

The builder runs over a seeded in-memory record store, the shared
FakeConfiguredSystems and FakeTenantVerifier, and IncidentCoreSettings built
from explicit values. Running the built upgrade shows the table name, the cap
and the tenants it was given: the entry point resolves those services in its
service scope and passes them in.
"""

import pytest

from features.incident.common.settings import IncidentCoreSettings
from features.incident.core.api import LegacyUpgrade, UpgradeReport, build_legacy_upgrade
from features.incident.core.store import incidents_table
from tests.factories.incident import SLACK_TENANT, CountingRecordStore, FakeConfiguredSystems
from tests.factories.legacy_upgrade import TENANTS, legacy_item, verified_slack

pytestmark = pytest.mark.unit

TABLE_NAME = "incidents-under-test"


def _records(*incident_ids: str) -> CountingRecordStore:
    records = CountingRecordStore()
    for incident_id in incident_ids:
        assert records.put(incidents_table(TABLE_NAME), legacy_item(incident_id)).is_success
    return records


def test_the_built_upgrade_reads_the_configured_table_with_the_configured_cap() -> None:
    settings = IncidentCoreSettings(incidents_table=TABLE_NAME, full_read_max_items=1)

    upgrade = build_legacy_upgrade(_records("inc-1", "inc-2"), FakeConfiguredSystems(TENANTS), verified_slack(), settings)
    report = upgrade.run(apply=False)

    assert isinstance(upgrade, LegacyUpgrade)
    assert isinstance(report, UpgradeReport)
    assert (report.failures, report.cap) == (("read_limit_exceeded",), 1)


def test_the_built_upgrade_stamps_the_configured_slack_tenant() -> None:
    records = _records("inc-1")
    settings = IncidentCoreSettings(incidents_table=TABLE_NAME)

    report = build_legacy_upgrade(records, FakeConfiguredSystems(TENANTS), verified_slack(), settings).run(apply=True)

    stored = records.get(incidents_table(TABLE_NAME), {"id": "inc-1"}).data
    assert report.upgraded == 1
    assert stored is not None and stored["conversation"]["tenant"] == SLACK_TENANT
