"""Unit tests for the jobs init() registers through the scheduler registry.

Stub strategy: the registry class in jobs.scheduled_tasks is replaced by a
recording BackgroundJobRegistry, so init() is observed only through the calls
it makes on the registry: the job name, the cadence, the schedule and the
lease TTL of each host and legacy job. The scheduler settings are the real
defaults (a 1800 s shared Tier-2 TTL) and the Slack tenant entry is set or
cleared through get_slack_settings. One test drives the real registry instead,
with the schedule library mocked and the lease store an in-memory LeaseStore,
to show the lease key a legacy job runs under.

Assertion rationale: init() must hand every job to the registry, which applies
the safe_run boundary and the lease, so the recorded registrations are the
whole schedule; the lease keys must stay scheduler:<job_name> so a lease held
by the previous deploy is still honoured.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from contracts.coordination import LeaseStore, ReadFailurePolicy
from contracts.services import ServiceScopeOpener
from infrastructure.coordination import InMemoryConditionalWriteStore
from integrations.slack.settings import SlackTenant
from jobs import scheduled_tasks
from jobs.scheduled_tasks import init

pytestmark = pytest.mark.unit

DEFAULT_TTL = timedelta(seconds=1800)


@dataclass(frozen=True)
class Registration:
    job_name: str
    cadence: str
    when: timedelta | str
    lease_ttl: timedelta | None
    job: Callable[[], None]


class RecordingRegistry:
    """BackgroundJobRegistry that records registrations instead of scheduling them."""

    def __init__(self, service_scopes: ServiceScopeOpener) -> None:
        self._service_scopes = service_scopes
        self.registrations: list[Registration] = []

    @property
    def service_scopes(self) -> ServiceScopeOpener:
        return self._service_scopes

    def register_daily(
        self, *, job_name: str, schedule: str, job: Callable[[], None], lease_ttl: timedelta | None = None
    ) -> None:
        self.registrations.append(Registration(job_name, "daily", schedule, lease_ttl, job))

    def register_interval(
        self, *, job_name: str, every: timedelta, job: Callable[[], None], lease_ttl: timedelta | None = None
    ) -> None:
        self.registrations.append(Registration(job_name, "interval", every, lease_ttl, job))


@pytest.fixture
def registries() -> Iterator[list[RecordingRegistry]]:
    built: list[RecordingRegistry] = []

    def build(service_scopes: ServiceScopeOpener) -> RecordingRegistry:
        registry = RecordingRegistry(service_scopes)
        built.append(registry)
        return registry

    with patch.object(scheduled_tasks, "_ScheduleBackgroundJobRegistry", side_effect=build):
        yield built


def _slack_tenant(monkeypatch: pytest.MonkeyPatch, tenant: SlackTenant | None) -> None:
    settings = MagicMock()
    settings.tenant = tenant
    monkeypatch.setattr("jobs.scheduled_tasks.get_slack_settings", lambda: settings)


def _by_name(registry: RecordingRegistry) -> dict[str, Registration]:
    return {registration.job_name: registration for registration in registry.registrations}


def test_init_registers_every_host_and_legacy_job_through_the_registry(
    registries: list[RecordingRegistry], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a Slack tenant, init() registers five jobs, each with its cadence and tier."""
    _slack_tenant(monkeypatch, SlackTenant(team_id="T0000TEST"))

    init(MagicMock(), MagicMock())

    (registry,) = registries
    registered = {(r.job_name, r.cadence, r.when, r.lease_ttl) for r in registry.registrations}
    assert registered == {
        ("scheduler_heartbeat", "interval", timedelta(minutes=5), None),
        ("integration_healthchecks", "interval", timedelta(minutes=5), None),
        ("provision_aws_identity_center", "interval", timedelta(hours=2), DEFAULT_TTL),
        ("notify_stale_incident_channels", "daily", "16:00", DEFAULT_TTL),
        ("spending_generate_spending_data", "daily", "00:00", DEFAULT_TTL),
    }
    jobs = _by_name(registry)
    assert jobs["scheduler_heartbeat"].job is scheduled_tasks.scheduler_heartbeat
    assert jobs["integration_healthchecks"].job is scheduled_tasks.integration_healthchecks
    assert jobs["provision_aws_identity_center"].job is scheduled_tasks.provision_aws_identity_center
    assert jobs["notify_stale_incident_channels"].job is scheduled_tasks.notify_stale_incident_channels_job


def test_init_skips_the_stale_channel_job_and_logs_why_without_a_slack_tenant(
    registries: list[RecordingRegistry], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without [slack.tenant] the nudge is not registered and the skip is logged at debug."""
    _slack_tenant(monkeypatch, None)

    with patch.object(scheduled_tasks, "logger") as logger:
        init(MagicMock(), MagicMock())

    (registry,) = registries
    assert set(_by_name(registry)) == {
        "scheduler_heartbeat",
        "integration_healthchecks",
        "provision_aws_identity_center",
        "spending_generate_spending_data",
    }
    logger.debug.assert_any_call(
        "scheduled_job_skipped", job_name="notify_stale_incident_channels", reason="slack_not_configured"
    )


def test_plugin_jobs_register_on_the_same_registry_after_the_host_jobs(
    registries: list[RecordingRegistry], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plugin callback receives the one registry, built with the host's scope opener, once the host jobs are in."""
    _slack_tenant(monkeypatch, None)
    service_scopes = MagicMock(name="scope_opener")
    seen: list[tuple[RecordingRegistry, int]] = []

    def register_plugin_jobs(registry: RecordingRegistry) -> None:
        seen.append((registry, len(registry.registrations)))

    init(register_plugin_jobs, service_scopes)

    (registry,) = registries
    assert seen == [(registry, 4)]
    assert registry.service_scopes is service_scopes


@patch("jobs.scheduled_tasks.get_slack_web_client")
def test_the_stale_channel_client_is_built_per_run_not_at_init(
    get_client: MagicMock, registries: list[RecordingRegistry], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Registering the nudge builds no Slack client; the job builds one when it runs."""
    _slack_tenant(monkeypatch, SlackTenant(team_id="T0000TEST"))

    init(MagicMock(), MagicMock())

    get_client.assert_not_called()


def test_a_legacy_job_runs_under_its_unchanged_lease_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Through the real registry, provision_aws_identity_center leases scheduler:provision_aws_identity_center for 1800 s."""
    _slack_tenant(monkeypatch, None)
    lease_store = LeaseStore(
        InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300),
        read_failure_policy=ReadFailurePolicy.FAIL_CLOSED,
    )
    body = MagicMock(__name__="provision_aws_identity_center", __module__="jobs.scheduled_tasks")

    with (
        patch.object(scheduled_tasks, "schedule_lib") as schedule_lib,
        patch.object(scheduled_tasks, "get_lease_store", return_value=lease_store) as get_lease_store,
        patch.object(scheduled_tasks, "provision_aws_identity_center", body),
    ):
        builders: dict[tuple[int, ...], MagicMock] = {}
        schedule_lib.every.side_effect = lambda *interval: builders.setdefault(interval, MagicMock())
        init(MagicMock(), MagicMock())
        (provision_registration,) = builders[(7200,)].seconds.do.call_args_list
        provision_run = provision_registration.args[0]

        held = lease_store.acquire("scheduler:provision_aws_identity_center")
        provision_run()
        body.assert_not_called()

        assert held is not None
        lease_store.release("scheduler:provision_aws_identity_center", held)
        provision_run()

    body.assert_called_once_with()
    get_lease_store.assert_any_call(1800)
