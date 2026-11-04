"""Unit tests for one run of the incident legacy upgrade job.

The job is the one the plugin registers, taken from a recording registry, so
the run under test is the scheduled one. Its scope opener is a fake resolving a
counting in-memory record store seeded with one legacy item, the configured
Slack and Google tenants and a verifier confirming the Slack tenant; the real
runner and bridge run over them. Assertions are on the scopes opened and closed
and on the writes the store recorded, which is what the mode controls; the
report itself is covered by the runner's tests.
"""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest

from contracts.records import RecordStore
from contracts.services import ServiceScopeOpener
from contracts.workplace import ConfiguredSystems, TenantVerifier
from features.incident.response import plugin
from features.incident.response.settings import get_incident_response_settings
from tests.factories.incident import FakeConfiguredSystems
from tests.factories.legacy_upgrade import TABLE, TENANTS, InterceptingRecordStore, legacy_item, records_with, verified_slack
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
    assert (scopes.opened, scopes.closed, records.writes) == (1, 1, ["update"])
    assert stored is not None and stored["record_version"] == 1


def test_each_run_opens_its_own_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    records = records_with(legacy_item())
    scopes = _scopes(records)
    job = _registered_job(monkeypatch, "apply", scopes)

    job()
    job()

    assert (scopes.opened, scopes.closed, records.writes) == (2, 2, ["update"])


def test_a_failed_resolution_propagates_and_still_closes_the_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """The job has no handler of its own: safe_run, around it, logs the failure once."""
    records = records_with(legacy_item())
    scopes = FakeServiceScopeOpener({RecordStore: records, ConfiguredSystems: FakeConfiguredSystems(TENANTS)})
    job = _registered_job(monkeypatch, "apply", scopes)

    with pytest.raises(KeyError):
        job()

    assert (scopes.opened, scopes.closed, records.writes) == (1, 1, [])
