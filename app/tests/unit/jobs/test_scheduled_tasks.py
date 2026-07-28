"""Unit tests for scheduled tasks job coordination.

Tests the scheduling logic, error handling, and task integration without
executing the actual scheduled work.
"""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.idempotency import IdempotencySettings, InMemoryIdempotencyStore
from jobs.scheduled_tasks import _tier2, init, reconcile_access_sync, safe_run, scheduler_heartbeat


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


class TestReconcileAccessSync:
    """Tests for the reconcile_access_sync scheduled job."""

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_access_runtime_config")
    @patch("jobs.scheduled_tasks.get_access_sync_coordinator")
    @patch("jobs.scheduled_tasks.logger")
    def test_reconcile_syncs_each_registered_platform(self, mock_logger, mock_get_coordinator, mock_get_runtime_config) -> None:
        """reconcile_access_sync calls sync_platform once per platform in config."""
        mock_coordinator = MagicMock()
        mock_get_coordinator.return_value = mock_coordinator
        mock_runtime_config = MagicMock()
        mock_runtime_config.platforms = {"aws": MagicMock(), "fake": MagicMock()}
        mock_get_runtime_config.return_value = mock_runtime_config

        reconcile_access_sync()

        assert mock_coordinator.sync_platform.call_count == 2
        called_platforms = {call.kwargs["platform"] for call in mock_coordinator.sync_platform.call_args_list}
        assert called_platforms == {"aws", "fake"}

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_access_runtime_config")
    @patch("jobs.scheduled_tasks.get_access_sync_coordinator")
    @patch("jobs.scheduled_tasks.logger")
    def test_reconcile_runs_with_dry_run_false(self, mock_logger, mock_get_coordinator, mock_get_runtime_config) -> None:
        """reconcile_access_sync always executes with dry_run=False."""
        mock_coordinator = MagicMock()
        mock_get_coordinator.return_value = mock_coordinator
        mock_runtime_config = MagicMock()
        mock_runtime_config.platforms = {"aws": MagicMock()}
        mock_get_runtime_config.return_value = mock_runtime_config

        reconcile_access_sync()

        mock_coordinator.sync_platform.assert_called_once_with(platform="aws", dry_run=False)

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_access_runtime_config")
    @patch("jobs.scheduled_tasks.get_access_sync_coordinator")
    @patch("jobs.scheduled_tasks.logger")
    def test_reconcile_no_platforms_does_nothing(self, mock_logger, mock_get_coordinator, mock_get_runtime_config) -> None:
        """reconcile_access_sync with an empty platforms map calls sync_platform zero times."""
        mock_coordinator = MagicMock()
        mock_get_coordinator.return_value = mock_coordinator
        mock_runtime_config = MagicMock()
        mock_runtime_config.platforms = {}
        mock_get_runtime_config.return_value = mock_runtime_config

        reconcile_access_sync()

        mock_coordinator.sync_platform.assert_not_called()

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_access_runtime_config")
    @patch("jobs.scheduled_tasks.get_access_sync_coordinator")
    @patch("jobs.scheduled_tasks.logger")
    def test_reconcile_logs_started(self, mock_logger, mock_get_coordinator, mock_get_runtime_config) -> None:
        """reconcile_access_sync emits a start log entry."""
        mock_get_coordinator.return_value = MagicMock()
        mock_runtime_config = MagicMock()
        mock_runtime_config.platforms = {}
        mock_get_runtime_config.return_value = mock_runtime_config

        reconcile_access_sync()

        mock_logger.info.assert_called_once_with("reconcile_access_sync_started", module="scheduled_tasks")


class TestTier2Wrapper:
    """Tests for the Tier-2 job lease wrapper."""

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_lease_store")
    def test_tier2_wrapper_executes_job_on_first_call(self, mock_get_lease_store) -> None:
        """_tier2(...)() executes the wrapped job on the first invocation."""
        # Provide a real in-memory store via the mock
        settings = IdempotencySettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=300)
        real_store = InMemoryIdempotencyStore(idempotency_settings=settings)
        mock_get_lease_store.return_value = real_store

        job = MagicMock()
        wrapped_job = _tier2("scheduler:test_job", job)

        wrapped_job()

        job.assert_called_once()

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_lease_store")
    def test_tier2_wrapper_skips_job_while_lease_held(self, mock_get_lease_store) -> None:
        """_tier2(...)() skips the job on a second invocation while the lease is held."""
        settings = IdempotencySettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=300)
        real_store = InMemoryIdempotencyStore(idempotency_settings=settings)
        mock_get_lease_store.return_value = real_store

        job = MagicMock()
        wrapped_job = _tier2("scheduler:test_job", job)

        # First call: job should execute
        wrapped_job()
        assert job.call_count == 1

        # Second call: job should NOT execute (lease is held)
        wrapped_job()
        assert job.call_count == 1  # Still 1, not 2

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_lease_store")
    def test_tier2_wrapper_retries_after_lease_expires(self, mock_get_lease_store) -> None:
        """_tier2(...)() re-executes the job after the lease expires."""
        # Build a store with zero TTL so the lease expires immediately
        settings = IdempotencySettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=0)
        real_store = InMemoryIdempotencyStore(idempotency_settings=settings)
        mock_get_lease_store.return_value = real_store

        job = MagicMock()
        wrapped_job = _tier2("scheduler:test_job", job)

        # First call: job executes
        wrapped_job()
        assert job.call_count == 1

        # Second call: lease has expired, job should re-execute
        wrapped_job()
        assert job.call_count == 2


class TestInitJobRegistration:
    """Tests for the scheduler init() job registration."""

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks._tier2")
    @patch("jobs.scheduled_tasks.get_plugin_manager")
    @patch("jobs.scheduled_tasks.schedule.every")
    @patch("jobs.scheduled_tasks.get_scheduler_settings")
    def test_init_registers_tier1_jobs_without_lease(
        self, mock_get_settings, mock_schedule_every, mock_get_pm, mock_tier2
    ) -> None:
        """init() registers Tier-1 jobs (scheduler_heartbeat, integration_healthchecks) without lease wrapping."""
        # Single shared default Tier-2 lease TTL (no per-job aggregator).
        mock_settings = MagicMock()
        mock_settings.DEFAULT_TIER2_LEASE_TTL_SECONDS = 1800
        mock_get_settings.return_value = mock_settings

        # Mock plugin manager
        mock_pm = MagicMock()
        mock_get_pm.return_value = mock_pm

        # Mock schedule builder
        mock_schedule = MagicMock()
        mock_schedule_every.return_value = mock_schedule

        # Mock bot
        mock_bot = MagicMock()

        init(mock_bot)

        # Only the 3 Tier-2 jobs go through the lease wrapper; the 2 Tier-1 jobs
        # (scheduler_heartbeat, integration_healthchecks) must be scheduled directly.
        assert mock_tier2.call_count == 3
        mock_pm.hook.register_background_jobs.assert_called_once()

    @pytest.mark.unit
    @patch("jobs.scheduled_tasks.get_plugin_manager")
    @patch("jobs.scheduled_tasks.schedule.every")
    @patch("jobs.scheduled_tasks.get_scheduler_settings")
    @patch("jobs.scheduled_tasks._tier2")
    def test_init_registers_tier2_jobs_with_lease(self, mock_tier2, mock_get_settings, mock_schedule_every, mock_get_pm) -> None:
        """init() registers Tier-2 jobs (provision_aws_identity_center, etc.) with lease wrapping via _tier2."""
        # Single shared default Tier-2 lease TTL (no per-job aggregator).
        mock_settings = MagicMock()
        mock_settings.DEFAULT_TIER2_LEASE_TTL_SECONDS = 1800
        mock_get_settings.return_value = mock_settings

        # Mock plugin manager
        mock_pm = MagicMock()
        mock_get_pm.return_value = mock_pm

        # Mock schedule builder
        mock_schedule = MagicMock()
        mock_schedule_every.return_value = mock_schedule

        # _tier2 returns a wrapped job
        mock_tier2.return_value = MagicMock()

        # Mock bot
        mock_bot = MagicMock()

        init(mock_bot)

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
