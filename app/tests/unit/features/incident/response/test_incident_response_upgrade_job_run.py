"""Unit tests for one run of the incident legacy upgrade job.

The job is the one the plugin registers, taken from a recording registry, so
the run under test is the scheduled one. Its scope opener is a fake resolving a
counting in-memory record store seeded with one legacy item, the configured
Slack and Google tenants and a verifier confirming the Slack tenant; the real
runner and bridge run over them. The legacy roles reader is substituted at
the response provider with the in-memory reader, which records the reports it
reads. Assertions are on the scopes opened and closed
and on the writes the store recorded, which is what the mode controls; the
report itself is covered by the runner's tests.
"""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest

from contracts.records import RecordStore
from contracts.services import ServiceScopeOpener
from contracts.workplace import ConfiguredSystems, TenantVerifier, WorkplaceSystem
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.adapters.in_memory import InMemoryLegacyRolesReader
from features.incident.core.adapters.incident_items import RECORD_VERSION
from features.incident.core.domain import ReportReference
from features.incident.response import plugin, providers
from features.incident.response.settings import get_incident_response_settings
from tests.factories.incident import FakeConfiguredSystems
from tests.factories.legacy_upgrade import (
    GOOGLE_TENANT,
    REPORT_URL,
    TABLE,
    TENANTS,
    InterceptingRecordStore,
    legacy_item,
    records_with,
    verified_slack,
)
from tests.factories.services import FakeServiceScopeOpener

pytestmark = pytest.mark.unit


class _SingleJobRegistry:
    """A BackgroundJobRegistry over ``scopes`` that keeps the one interval job registered."""

    def __init__(self, scopes: FakeServiceScopeOpener) -> None:
        self._scopes = scopes
        self.job: Callable[[], None] | None = None

    @property
    def service_scopes(self) -> ServiceScopeOpener:
        return self._scopes

    def register_daily(self, **_: Any) -> None:
        raise AssertionError("unexpected daily job")

    def register_interval(
        self, *, job_name: str, every: timedelta, job: Callable[[], None], lease_ttl: timedelta | None = None
    ) -> None:
        self.job = job


@pytest.fixture(autouse=True)
def _fresh_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("INCIDENT_RESPONSE__UPGRADE_MODE", raising=False)
    get_incident_response_settings.cache_clear()
    yield
    get_incident_response_settings.cache_clear()


def _scopes(records: InterceptingRecordStore) -> FakeServiceScopeOpener:
    return FakeServiceScopeOpener(
        {RecordStore: records, ConfiguredSystems: FakeConfiguredSystems(TENANTS), TenantVerifier: verified_slack()}
    )


def _registered_job(monkeypatch: pytest.MonkeyPatch, mode: str, scopes: FakeServiceScopeOpener) -> Callable[[], None]:
    monkeypatch.setenv("INCIDENT_RESPONSE__UPGRADE_MODE", mode)
    registry = _SingleJobRegistry(scopes)
    plugin.register_background_jobs(registry)
    assert registry.job is not None
    return registry.job


def test_a_dry_run_opens_one_scope_and_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    records = records_with(legacy_item())
    scopes = _scopes(records)

    _registered_job(monkeypatch, "dry_run", scopes)()

    assert (scopes.opened, scopes.closed, records.writes) == (1, 1, [])


def test_an_apply_run_opens_one_scope_and_upgrades_the_item(monkeypatch: pytest.MonkeyPatch) -> None:
    records = records_with(legacy_item("inc-1"))
    scopes = _scopes(records)

    _registered_job(monkeypatch, "apply", scopes)()

    stored = records.get(TABLE, {"id": "inc-1"}).data
    assert (scopes.opened, scopes.closed, records.writes) == (1, 1, ["put_if_not_exists", "update"])
    assert stored is not None and stored["record_version"] == RECORD_VERSION


def test_each_run_opens_its_own_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    records = records_with(legacy_item())
    scopes = _scopes(records)
    job = _registered_job(monkeypatch, "apply", scopes)

    job()
    job()

    assert (scopes.opened, scopes.closed, records.writes) == (2, 2, ["put_if_not_exists", "update"])


def test_a_failed_resolution_propagates_and_still_closes_the_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """The job has no handler of its own: safe_run, around it, logs the failure once."""
    records = records_with(legacy_item())
    scopes = FakeServiceScopeOpener({RecordStore: records, ConfiguredSystems: FakeConfiguredSystems(TENANTS)})
    job = _registered_job(monkeypatch, "apply", scopes)

    with pytest.raises(KeyError):
        job()

    assert (scopes.opened, scopes.closed, records.writes) == (1, 1, [])


def test_an_apply_run_maps_a_roleless_items_roles_through_the_legacy_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two roleless items are read in one run: both reads run on the run's one event loop."""
    report = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="doc123", url=REPORT_URL)
    legacy = InMemoryLegacyRolesReader()
    legacy.seed(report, {IncidentRole.INCIDENT_COMMANDER: "U0IC"})
    monkeypatch.setattr(providers, "legacy_roles_reader", lambda: legacy)
    no_roles: dict[str, Any] = {"incident_commander": None, "operations_lead": None}
    records = records_with(legacy_item("inc-1", **no_roles), legacy_item("inc-2", **no_roles))

    _registered_job(monkeypatch, "apply", _scopes(records))()

    stored = [records.get(TABLE, {"id": incident_id}).data for incident_id in ("inc-1", "inc-2")]
    assert legacy.reads == [report, report]
    assert [item["incident_commander"] for item in stored if item is not None] == ["U0IC", "U0IC"]
