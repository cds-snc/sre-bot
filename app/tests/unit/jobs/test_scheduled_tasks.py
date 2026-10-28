"""Unit tests for scheduled tasks job coordination.

Tests the scheduling logic, error handling, and task integration without
executing the actual scheduled work.
"""

from datetime import timedelta
from unittest.mock import MagicMock, create_autospec, patch

import pytest

from contracts.coordination import LeaseStore, ReadFailurePolicy
from infrastructure.coordination import InMemoryConditionalWriteStore
from integrations.slack.settings import SlackTenant
from jobs.scheduled_tasks import (
    _ScheduleBackgroundJobRegistry,
    _tier2,
    init,
    notify_stale_incident_channels_job,
    safe_run,
    scheduler_heartbeat,
)
from modules.aws import spending


class TestSafeRun:
    """Tests for the safe_run error handling wrapper."""

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.logger")
    def test_safe_run_executes_job_successfully(self, mock_logger) -> None:
        """Test that safe_run executes a successful job without logging errors."""
        job = MagicMock()
        job.__module__ = "test_module"
        job.__name__ = "test_job"

        wrapper = safe_run(job)
        wrapper()

        job.assert_called_once()
        mock_logger.error.assert_not_called()

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.logger")
    def test_safe_run_catches_exception(self, mock_logger) -> None:
        """Test that safe_run catches and logs exceptions."""

        def failing_job():
            raise ValueError("Test error")

        failing_job.__module__ = "test_module"
        failing_job.__name__ = "failing_job"

        wrapper = safe_run(failing_job)
        wrapper()

        # Verify error was logged with context
        assert mock_logger.error.call_count == 1
        error_call = mock_logger.error.call_args
        assert error_call[0][0] == "safe_run_error"
        assert error_call[1]["error"] == "Test error"
        assert error_call[1]["function"] == "failing_job"
        assert error_call[1]["module"] == "test_module"

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.logger")
    def test_safe_run_preserves_job_arguments(self, mock_logger) -> None:
        """Test that safe_run passes through job arguments and kwargs."""
        job = MagicMock()
        job.__module__ = "test_module"
        job.__name__ = "test_job"

        wrapper = safe_run(job)
        wrapper("arg1", "arg2", kwarg1="value1", kwarg2="value2")

        job.assert_called_once_with("arg1", "arg2", kwarg1="value1", kwarg2="value2")

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.logger")
    def test_safe_run_logs_arguments_on_exception(self, mock_logger) -> None:
        """Test that safe_run logs job arguments when exception occurs."""

        def failing_job(arg1, kwargs_dict):
            raise RuntimeError("Failed")

        failing_job.__module__ = "test_module"
        failing_job.__name__ = "failing_job"

        wrapper = safe_run(failing_job)
        wrapper("test_arg", {"key": "value"})

        error_call = mock_logger.error.call_args
        assert error_call[1]["job_args"] == ("test_arg", {"key": "value"})


class TestSchedulerHeartbeat:
    """Tests for scheduler heartbeat logging."""

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.time")
    @patch("jobs.scheduled_tasks.logger")
    def test_scheduler_heartbeat_logs_current_time(self, mock_logger, mock_time) -> None:
        """Test that scheduler_heartbeat logs the current time."""
        mock_time.ctime.return_value = "Thu Feb  6 10:30:00 2026"

        scheduler_heartbeat()

        assert mock_logger.info.call_count == 1
        log_call = mock_logger.info.call_args
        assert log_call[0][0] == "running_scheduler_heartbeat"
        assert log_call[1]["module"] == "scheduled_tasks"
        assert "10:30:00" in log_call[1]["time"]

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.time")
    @patch("jobs.scheduled_tasks.logger")
    def test_scheduler_heartbeat_calls_ctime(self, mock_logger, mock_time) -> None:
        """Test that scheduler_heartbeat calls time.ctime()."""
        scheduler_heartbeat()

        mock_time.ctime.assert_called_once()


class TestScheduleBackgroundJobRegistry:
    """Tests for the typed background-job registry methods."""

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.schedule_lib")
    def test_register_daily_binds_hh_mm(self, mock_schedule_lib) -> None:
        registry = _ScheduleBackgroundJobRegistry(service_scopes=MagicMock(name="scope_opener"))
        job = MagicMock()

        registry.register_daily(job_name="daily_job", schedule="03:30", job=job)

        mock_schedule_lib.every.assert_called_once_with()
        mock_schedule_lib.every.return_value.day.at.assert_called_once_with("03:30")
        mock_schedule_lib.every.return_value.day.at.return_value.do.assert_called_once()

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.schedule_lib")
    def test_register_interval_with_minutes(self, mock_schedule_lib) -> None:
        registry = _ScheduleBackgroundJobRegistry(service_scopes=MagicMock(name="scope_opener"))
        job = MagicMock()

        registry.register_interval(job_name="minute_job", every=timedelta(minutes=5), job=job)

        mock_schedule_lib.every.assert_called_once_with(300)
        mock_schedule_lib.every.return_value.seconds.do.assert_called_once()

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.schedule_lib")
    def test_register_interval_with_hours(self, mock_schedule_lib) -> None:
        registry = _ScheduleBackgroundJobRegistry(service_scopes=MagicMock(name="scope_opener"))
        job = MagicMock()

        registry.register_interval(job_name="hourly_job", every=timedelta(hours=2), job=job)

        mock_schedule_lib.every.assert_called_once_with(7200)
        mock_schedule_lib.every.return_value.seconds.do.assert_called_once()

    @pytest.mark.unit
    def test_registry_exposes_the_opener_it_was_built_with(self) -> None:
        """registry.service_scopes returns the opener passed at construction, by identity.

        Stub strategy: the opener is a bare MagicMock because the registry only
        stores and returns it; the schedule library is not touched.
        Assertion rationale: identity shows the registry adds no wrapper, so a
        scheduled job opens its scope from the same host opener as the Slack
        registrar.
        """
        opener = MagicMock(name="scope_opener")

        registry = _ScheduleBackgroundJobRegistry(service_scopes=opener)

        assert registry.service_scopes is opener


class TestTier2Wrapper:
    """Tests for the Tier-2 job lease wrapper."""

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_lease_store")
    def test_tier2_wrapper_executes_job_on_first_call(self, mock_get_lease_store) -> None:
        """_tier2(...)() executes the wrapped job on the first invocation."""
        # Provide a real in-memory store via the mock
        real_store = LeaseStore(
            InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300),
            read_failure_policy=ReadFailurePolicy.FAIL_CLOSED,
        )
        mock_get_lease_store.return_value = real_store

        job = MagicMock()
        wrapped_job = _tier2("scheduler:test_job", job)

        wrapped_job()

        job.assert_called_once()

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_lease_store")
    def test_tier2_wrapper_skips_job_when_lease_already_held(self, mock_get_lease_store) -> None:
        """_tier2(...)() skips execution when another runner already holds the lease."""
        real_store = LeaseStore(
            InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300),
            read_failure_policy=ReadFailurePolicy.FAIL_CLOSED,
        )
        mock_get_lease_store.return_value = real_store

        # Simulate another replica already holding the lease.
        assert real_store.acquire("scheduler:test_job") is not None

        job = MagicMock()
        wrapped_job = _tier2("scheduler:test_job", job)

        # The wrapped call should skip because lease is already held.
        wrapped_job()
        job.assert_not_called()

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_lease_store")
    def test_tier2_wrapper_retries_after_lease_expires(self, mock_get_lease_store) -> None:
        """_tier2(...)() re-executes the job after the lease expires."""
        # Build a store with zero TTL so the lease expires immediately
        real_store = LeaseStore(
            InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=0),
            read_failure_policy=ReadFailurePolicy.FAIL_CLOSED,
        )
        mock_get_lease_store.return_value = real_store

        job = MagicMock()
        wrapped_job = _tier2("scheduler:test_job", job)

        # First call: job executes
        wrapped_job()
        assert job.call_count == 1

        # Second call: lease has expired, job should re-execute
        wrapped_job()
        assert job.call_count == 2


@pytest.fixture
def slack_tenant(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Configure a [slack.tenant] entry for the stale-channel job."""
    settings = MagicMock()
    settings.tenant = SlackTenant(team_id="T0000TEST")
    monkeypatch.setattr("jobs.scheduled_tasks.get_slack_settings", lambda: settings)
    return settings


@pytest.mark.usefixtures("slack_tenant")
class TestInitJobRegistration:
    """Tests for the scheduler init() job registration, with a Slack tenant configured."""

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks._tier2")
    @patch("jobs.scheduled_tasks.schedule.every")
    @patch("jobs.scheduled_tasks.get_scheduler_settings")
    def test_init_registers_tier1_jobs_without_lease(self, mock_get_settings, mock_schedule_every, mock_tier2) -> None:
        """init() registers Tier-1 jobs (scheduler_heartbeat, integration_healthchecks) without lease wrapping."""
        # Single shared default Tier-2 lease TTL (no per-job aggregator).
        mock_settings = MagicMock()
        mock_settings.default_tier2_lease_ttl_seconds = 1800
        mock_get_settings.return_value = mock_settings

        # Plugin job registration callable handed in by the host
        register_plugin_jobs = MagicMock()

        # Mock schedule builder
        mock_schedule = MagicMock()
        mock_schedule_every.return_value = mock_schedule

        service_scopes = MagicMock(name="scope_opener")
        init(register_plugin_jobs, service_scopes)

        # Only the 3 Tier-2 jobs go through the lease wrapper; the 2 Tier-1 jobs
        # (scheduler_heartbeat, integration_healthchecks) must be scheduled directly.
        assert mock_tier2.call_count == 3
        register_plugin_jobs.assert_called_once()
        (registry,) = register_plugin_jobs.call_args.args
        assert isinstance(registry, _ScheduleBackgroundJobRegistry)
        assert registry.service_scopes is service_scopes

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.schedule.every")
    @patch("jobs.scheduled_tasks.get_scheduler_settings")
    @patch("jobs.scheduled_tasks._tier2")
    def test_init_registers_tier2_jobs_with_lease(self, mock_tier2, mock_get_settings, mock_schedule_every) -> None:
        """init() registers Tier-2 jobs (provision_aws_identity_center, etc.) with lease wrapping via _tier2."""
        # Single shared default Tier-2 lease TTL (no per-job aggregator).
        mock_settings = MagicMock()
        mock_settings.default_tier2_lease_ttl_seconds = 1800
        mock_get_settings.return_value = mock_settings

        # Plugin job registration callable handed in by the host
        register_plugin_jobs = MagicMock()

        # Mock schedule builder
        mock_schedule = MagicMock()
        mock_schedule_every.return_value = mock_schedule

        # _tier2 returns a wrapped job
        mock_tier2.return_value = MagicMock()

        init(register_plugin_jobs, MagicMock())

        # Each Tier-2 job goes through _tier2 with its own lease key. The TTL is
        # NOT passed per call: _tier2 reads the single shared default internally,
        # so there is no per-job TTL argument.
        called_lease_keys = {call.args[0] for call in mock_tier2.call_args_list}
        assert called_lease_keys == {
            "scheduler:provision_aws_identity_center",
            "scheduler:notify_stale_incident_channels",
            "scheduler:spending_generate_spending_data",
        }
        assert mock_tier2.call_count == 3

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.logger")
    @patch("jobs.scheduled_tasks.spending")
    @patch("jobs.scheduled_tasks.notify_stale_incident_channels")
    @patch("jobs.scheduled_tasks.get_lease_store")
    @patch("jobs.scheduled_tasks.schedule.every")
    @patch("jobs.scheduled_tasks.get_scheduler_settings")
    def test_init_daily_spending_job_runs_update_job_without_arguments(
        self,
        mock_get_settings,
        mock_schedule_every,
        mock_get_lease_store,
        mock_notify_stale_incident_channels,
        mock_spending,
        mock_logger,
    ) -> None:
        """The daily spending job runs the spending update job cleanly when the scheduler fires it.

        Stub strategy: schedule.every() is a MagicMock, so every daily .do()
        registration and its recorded args/kwargs are observable; _tier2 is real
        and backed by an in-memory lease store, so the wrapped job really runs.
        The spending module is replaced by functions autospecced from the real
        ones, so an argument the real signature rejects raises TypeError exactly
        as it would in production, and safe_run's module logger is patched to
        observe the error it would otherwise swallow.

        Assertion rationale: invoking each daily registration with the args and
        kwargs it was registered with mirrors what the schedule library does at
        run time. The update job must run once with no arguments, the
        generate-only function must not be the scheduled job, and no
        safe_run_error may be logged.
        """
        # Arrange
        mock_get_settings.return_value.default_tier2_lease_ttl_seconds = 1800
        mock_get_lease_store.return_value = LeaseStore(
            InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300),
            read_failure_policy=ReadFailurePolicy.FAIL_CLOSED,
        )
        mock_spending.generate_spending_data = create_autospec(spending.generate_spending_data)
        mock_spending.execute_spending_data_update_job = create_autospec(spending.execute_spending_data_update_job)

        init(MagicMock(), MagicMock())

        # Act
        daily_registrations = mock_schedule_every.return_value.day.at.return_value.do.call_args_list
        for registration in daily_registrations:
            job, *job_args = registration.args
            job(*job_args, **registration.kwargs)

        # Assert
        mock_spending.execute_spending_data_update_job.assert_called_once_with()
        mock_spending.generate_spending_data.assert_not_called()
        assert not [call for call in mock_logger.error.call_args_list if call.args[:1] == ("safe_run_error",)]


class TestStaleIncidentChannelsJob:
    """The stale-channel job runs on the outbound Slack Web API client, only when a Slack tenant is configured.

    Stub strategy: schedule.every() and _tier2 are MagicMocks so registrations are
    observable; get_slack_settings is replaced to set or clear the tenant entry,
    and get_slack_web_client to observe when the client is built.
    """

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_slack_web_client")
    @patch("jobs.scheduled_tasks._tier2")
    @patch("jobs.scheduled_tasks.schedule.every")
    def test_init_schedules_the_job_without_building_a_client_when_a_tenant_is_configured(
        self, mock_schedule_every, mock_tier2, mock_get_client, slack_tenant
    ) -> None:
        """The job is leased and scheduled daily at 16:00; the client is built per run, not at init."""
        init(MagicMock(), MagicMock())

        lease_jobs = {call.args[0]: call.args[1] for call in mock_tier2.call_args_list}
        assert lease_jobs["scheduler:notify_stale_incident_channels"] is notify_stale_incident_channels_job
        mock_schedule_every.return_value.day.at.assert_any_call("16:00")
        mock_get_client.assert_not_called()

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.notify_stale_incident_channels")
    @patch("jobs.scheduled_tasks.get_slack_web_client")
    def test_each_run_uses_a_fresh_web_api_client(self, mock_get_client, mock_notify) -> None:
        """A run hands the integrations/slack bot client to the legacy job."""
        notify_stale_incident_channels_job()

        mock_get_client.assert_called_once_with()
        mock_notify.assert_called_once_with(client=mock_get_client.return_value)

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.logger")
    @patch("jobs.scheduled_tasks._tier2")
    @patch("jobs.scheduled_tasks.schedule.every")
    def test_init_skips_the_job_and_logs_why_when_no_tenant_is_configured(
        self, mock_schedule_every, mock_tier2, mock_logger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without [slack.tenant] the job is never scheduled and the skip is logged at info."""
        settings = MagicMock()
        settings.tenant = None
        monkeypatch.setattr("jobs.scheduled_tasks.get_slack_settings", lambda: settings)

        init(MagicMock(), MagicMock())

        lease_keys = {call.args[0] for call in mock_tier2.call_args_list}
        assert "scheduler:notify_stale_incident_channels" not in lease_keys
        assert len(lease_keys) == 2
        mock_logger.info.assert_any_call(
            "scheduled_job_skipped", job_name="notify_stale_incident_channels", reason="slack_not_configured"
        )
