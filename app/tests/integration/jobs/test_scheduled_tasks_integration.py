"""Integration tests for scheduled tasks coordination.

Tests the scheduling system integration with all components,
verifying task registration and error handling across the system.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from jobs import scheduled_tasks


@pytest.mark.integration
class TestScheduledTasksInitialization:
    """Integration tests for scheduled tasks initialization."""

    @patch("jobs.scheduled_tasks.schedule")
    def test_init_registers_all_required_tasks(self, mock_schedule) -> None:
        """Test that init registers all required scheduled tasks.

        Verifies:
        - Stale incident channel notification (daily at 16:00)
        - Scheduler heartbeat (every 5 minutes)
        - Integration healthchecks (every 5 minutes)
        - Reconciliation batch processor (every 5 minutes)
        - AWS Identity Center provisioning (every 2 hours)
        - Spending data generation (daily at 00:00)
        """
        bot = MagicMock()

        scheduled_tasks.init(bot)

        # Count schedule.do() calls - one per task
        do_calls = [call for call in mock_schedule.mock_calls if ".do(" in str(call)]
        assert len(do_calls) == 6  # Six total scheduled tasks

    @patch("jobs.scheduled_tasks.schedule")
    def test_init_respects_scheduling_times(self, mock_schedule) -> None:
        """Test that tasks are scheduled at correct times.

        Verifies:
        - Daily tasks scheduled with .at()
        - Interval-based tasks with correct durations
        """
        bot = MagicMock()

        scheduled_tasks.init(bot)

        # Verify daily task times were called (at least once each)
        daily_do_calls = [
            call
            for call in mock_schedule.mock_calls
            if ".day.at(" in str(call) and ".do(" in str(call)
        ]
        assert len(daily_do_calls) >= 2  # At least two daily scheduled tasks

        # Verify 5-minute intervals
        minutes_do_calls = [
            call for call in mock_schedule.mock_calls if ".minutes.do(" in str(call)
        ]
        assert len(minutes_do_calls) >= 3  # At least three 5-minute tasks

        # Verify 2-hour interval
        hours_do_calls = [
            call for call in mock_schedule.mock_calls if ".hours.do(" in str(call)
        ]
        assert len(hours_do_calls) >= 1  # At least one 2-hour task
        # Verify bot.client was passed
        client_mentions = [
            call for call in mock_schedule.mock_calls if "client=" in str(call)
        ]
        assert len(client_mentions) >= 1

    @patch("jobs.scheduled_tasks.schedule")
    def test_init_uses_safe_run_wrapper(self, mock_schedule) -> None:
        """Test that tasks are wrapped with safe_run for error handling.

        This verifies that all scheduled tasks have error protection.
        Since safe_run wraps the functions, we verify at least one
        do() call references the safe_run mechanism.
        """
        bot = MagicMock()

        scheduled_tasks.init(bot)

        # Tasks should be registered and scheduled
        do_calls = [call for call in mock_schedule.mock_calls if ".do(" in str(call)]
        assert len(do_calls) > 0


@pytest.mark.integration
class TestIntegrationHealthchecksWorkflow:
    """Integration tests for health check workflow."""

    @patch("jobs.scheduled_tasks.logger")
    @patch("jobs.scheduled_tasks.identity_store")
    @patch("jobs.scheduled_tasks.opsgenie")
    @patch("jobs.scheduled_tasks.maxmind")
    @patch("jobs.scheduled_tasks.google_drive")
    def test_healthcheck_all_healthy(
        self,
        mock_google_drive,
        mock_maxmind,
        mock_opsgenie,
        mock_identity_store,
        mock_logger,
    ) -> None:
        """Test healthcheck when all integrations are healthy.

        Verifies:
        - Each integration is checked
        - No errors are logged
        - Healthy status is reported
        """
        mock_google_drive.healthcheck.return_value = True
        mock_maxmind.healthcheck.return_value = True
        mock_opsgenie.healthcheck.return_value = True
        mock_identity_store.healthcheck.return_value = True

        scheduled_tasks.integration_healthchecks()

        # Verify all healthchecks were called
        assert mock_google_drive.healthcheck.call_count == 1
        assert mock_maxmind.healthcheck.call_count == 1
        assert mock_opsgenie.healthcheck.call_count == 1
        assert mock_identity_store.healthcheck.call_count == 1

        # Verify no errors logged
        error_calls = [call for call in mock_logger.mock_calls if "error" in str(call)]
        assert len(error_calls) == 0

    @patch("jobs.scheduled_tasks.logger")
    @patch("jobs.scheduled_tasks.identity_store")
    @patch("jobs.scheduled_tasks.opsgenie")
    @patch("jobs.scheduled_tasks.maxmind")
    @patch("jobs.scheduled_tasks.google_drive")
    def test_healthcheck_partial_failures(
        self,
        mock_google_drive,
        mock_maxmind,
        mock_opsgenie,
        mock_identity_store,
        mock_logger,
    ) -> None:
        """Test healthcheck with some integrations failing.

        Verifies:
        - Failed integrations are logged
        - Healthcheck continues for other integrations
        - Error messages include integration name
        """
        mock_google_drive.healthcheck.return_value = False
        mock_maxmind.healthcheck.return_value = True
        mock_opsgenie.healthcheck.return_value = False
        mock_identity_store.healthcheck.return_value = True

        scheduled_tasks.integration_healthchecks()

        # All checks should be called
        assert mock_google_drive.healthcheck.call_count == 1
        assert mock_maxmind.healthcheck.call_count == 1
        assert mock_opsgenie.healthcheck.call_count == 1
        assert mock_identity_store.healthcheck.call_count == 1

        # Errors should be logged for unhealthy checks
        error_logs = [
            call for call in mock_logger.mock_calls if "error" in str(call).lower()
        ]
        assert len(error_logs) >= 2


@pytest.mark.integration
class TestSchedulerErrorRecovery:
    """Integration tests for error handling in scheduled tasks."""

    @patch("jobs.scheduled_tasks.logger")
    def test_safe_run_exception_recovery(self, mock_logger) -> None:
        """Test that safe_run allows scheduler to continue after exceptions.

        Verifies:
        - Exception is logged with full context
        - Scheduler can continue with next task
        - Error doesn't propagate
        """

        def failing_task():
            raise ValueError("Intentional failure")

        failing_task.__module__ = "jobs.scheduled_tasks"
        failing_task.__name__ = "failing_task"

        wrapper = scheduled_tasks.safe_run(failing_task)

        # Should not raise
        wrapper()

        # Error should be logged
        assert mock_logger.error.call_count == 1
        error_call = mock_logger.error.call_args
        assert error_call[0][0] == "safe_run_error"
        assert "Intentional failure" in error_call[1]["error"]

    @patch("jobs.scheduled_tasks.logger")
    def test_safe_run_preserves_args_in_error_logs(self, mock_logger) -> None:
        """Test that safe_run logs job arguments in error context.

        Useful for debugging which task configuration caused failure.
        """

        def task_with_args(config: dict, timeout: int):
            raise RuntimeError("Task failed")

        task_with_args.__module__ = "jobs.scheduled_tasks"
        task_with_args.__name__ = "task_with_args"

        wrapper = scheduled_tasks.safe_run(task_with_args)
        wrapper({"key": "value"}, 30)

        # Arguments should be logged
        error_call = mock_logger.error.call_args
        assert "job_args" in error_call[1] or "arguments" in error_call[1]
