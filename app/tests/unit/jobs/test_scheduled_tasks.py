"""Unit tests for scheduled tasks job coordination.

Tests the scheduling logic, error handling, and task integration without
executing the actual scheduled work.
"""

from unittest.mock import MagicMock, patch

import pytest

from jobs.scheduled_tasks import reconcile_access_sync, safe_run, scheduler_heartbeat


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
