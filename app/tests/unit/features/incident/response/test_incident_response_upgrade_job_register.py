"""Unit tests for the incident.response plugin's hookimpls: the legacy upgrade job registration and the requirements.

The hookimpls are called directly with a recording registry that keeps every
registration it is handed, over a fake scope opener; the settings come from the
installed ci configuration files with the mode, interval and lease set through
their environment overrides. Assertions are on what reaches the registry (job
name, cadence, lease) because the scheduler adapter's own behaviour is covered by
the jobs tests. Importing the module is checked against the schedule library's
own job list, which is what a registration at import would fill.
"""

import importlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import timedelta

import pytest
import schedule

from contracts.plugins.requirements import Requirement
from contracts.services import ServiceScopeOpener
from features.incident.response import plugin
from features.incident.response.settings import get_incident_response_settings
from tests.factories.services import FakeServiceScopeOpener

pytestmark = pytest.mark.unit

_MODE = "INCIDENT_RESPONSE__UPGRADE_MODE"


@dataclass(frozen=True)
class _Registration:
    job_name: str
    every: timedelta
    job: Callable[[], None]
    lease_ttl: timedelta | None


class _RecordingRegistry:
    """A BackgroundJobRegistry that keeps each interval registration and rejects daily ones."""

    def __init__(self) -> None:
        self.registrations: list[_Registration] = []
        self._scopes = FakeServiceScopeOpener({})

    @property
    def service_scopes(self) -> ServiceScopeOpener:
        return self._scopes

    def register_daily(
        self, *, job_name: str, schedule: str, job: Callable[[], None], lease_ttl: timedelta | None = None
    ) -> None:
        raise AssertionError(f"unexpected daily job {job_name}")

    def register_interval(
        self, *, job_name: str, every: timedelta, job: Callable[[], None], lease_ttl: timedelta | None = None
    ) -> None:
        self.registrations.append(_Registration(job_name, every, job, lease_ttl))


@pytest.fixture(autouse=True)
def _fresh_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in ("UPGRADE_MODE", "UPGRADE_INTERVAL_MINUTES", "UPGRADE_LEASE_TTL_SECONDS"):
        monkeypatch.delenv(f"INCIDENT_RESPONSE__{key}", raising=False)
    get_incident_response_settings.cache_clear()
    yield
    get_incident_response_settings.cache_clear()


def test_mode_off_registers_nothing() -> None:
    registry = _RecordingRegistry()

    plugin.register_background_jobs(registry)

    assert registry.registrations == []


@pytest.mark.parametrize("mode", ["dry_run", "apply"])
def test_a_run_mode_registers_one_leased_interval_job(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv(_MODE, mode)
    monkeypatch.setenv("INCIDENT_RESPONSE__UPGRADE_INTERVAL_MINUTES", "7")
    monkeypatch.setenv("INCIDENT_RESPONSE__UPGRADE_LEASE_TTL_SECONDS", "120")
    registry = _RecordingRegistry()

    plugin.register_background_jobs(registry)

    assert [(r.job_name, r.every, r.lease_ttl) for r in registry.registrations] == [
        ("incident_legacy_upgrade", timedelta(minutes=7), timedelta(seconds=120))
    ]


def test_the_default_cadence_is_thirty_minutes_under_a_fifteen_minute_lease(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_MODE, "dry_run")
    registry = _RecordingRegistry()

    plugin.register_background_jobs(registry)

    assert [(r.every, r.lease_ttl) for r in registry.registrations] == [(timedelta(minutes=30), timedelta(seconds=900))]


def test_the_registered_job_names_its_own_module_for_the_error_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """safe_run logs the module and name of the job it wraps, so the job must carry both."""
    monkeypatch.setenv(_MODE, "apply")
    registry = _RecordingRegistry()

    plugin.register_background_jobs(registry)

    job = registry.registrations[0].job
    assert (job.__module__, job.__name__) == ("features.incident.response.plugin", "incident_legacy_upgrade")


def test_the_plugin_requires_the_slack_and_google_tenants_and_the_handbook_id() -> None:
    assert plugin.register_requirements() == (
        Requirement("slack.tenant"),
        Requirement("google_workspace.tenant"),
        Requirement("incident_response.handbook_id"),
    )


def test_importing_the_plugin_schedules_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_MODE, "apply")
    before = list(schedule.get_jobs())

    importlib.reload(plugin)

    assert schedule.get_jobs() == before
