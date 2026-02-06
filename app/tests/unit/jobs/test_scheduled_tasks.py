"""Unit tests for scheduled tasks job coordination.

Tests the scheduling logic, error handling, and task integration without
executing the actual scheduled work.
"""

from unittest.mock import MagicMock, patch
from jobs.scheduled_tasks import safe_run, scheduler_heartbeat, run_continuously


class TestSafeRun:
    """Tests for the safe_run error handling wrapper."""

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

    @patch("jobs.scheduled_tasks.logger")
    def test_safe_run_preserves_job_arguments(self, mock_logger) -> None:
        """Test that safe_run passes through job arguments and kwargs."""
        job = MagicMock()
        job.__module__ = "test_module"
        job.__name__ = "test_job"

        wrapper = safe_run(job)
        wrapper("arg1", "arg2", kwarg1="value1", kwarg2="value2")

        job.assert_called_once_with("arg1", "arg2", kwarg1="value1", kwarg2="value2")

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

    @patch("jobs.scheduled_tasks.time")
    @patch("jobs.scheduled_tasks.logger")
    def test_scheduler_heartbeat_logs_current_time(
        self, mock_logger, mock_time
    ) -> None:
        """Test that scheduler_heartbeat logs the current time."""
        mock_time.ctime.return_value = "Thu Feb  6 10:30:00 2026"

        scheduler_heartbeat()

        assert mock_logger.info.call_count == 1
        log_call = mock_logger.info.call_args
        assert log_call[0][0] == "running_scheduler_heartbeat"
        assert log_call[1]["module"] == "scheduled_tasks"
        assert "10:30:00" in log_call[1]["time"]

    @patch("jobs.scheduled_tasks.time")
    @patch("jobs.scheduled_tasks.logger")
    def test_scheduler_heartbeat_calls_ctime(self, mock_logger, mock_time) -> None:
        """Test that scheduler_heartbeat calls time.ctime()."""
        scheduler_heartbeat()

        mock_time.ctime.assert_called_once()


class TestRunContinuously:
    """Tests for continuous run loop."""

    def test_run_continuously_returns_event(self) -> None:
        """Test that run_continuously returns a threading.Event.

        Note: Full mocking of run_continuously is complex due to the
        nested ScheduleThread class. This test verifies the function
        can be called without errors and returns the correct type.
        """
        # This is an integration test - it actually starts a thread
        result = run_continuously(interval=1440)  # 24 hour interval so it barely runs

        # Verify it returns an Event object
        assert hasattr(result, "is_set")
        assert hasattr(result, "set")

        # Stop the thread
        result.set()
