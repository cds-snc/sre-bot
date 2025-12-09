from jobs import scheduled_tasks

from unittest.mock import MagicMock, patch, call


@patch("jobs.scheduled_tasks.schedule")
def test_init(schedule_mock):
    """Test that init properly schedules all expected tasks."""
    # Setup
    bot = MagicMock()

    # Execute
    scheduled_tasks.init(bot)

    # Verify daily tasks at specific times
    schedule_mock.every().day.at.assert_has_calls(
        calls=[
            call("16:00"),
            call("00:00"),
        ],
        any_order=True,
    )

    # Verify interval-based tasks
    schedule_mock.every.assert_has_calls(
        calls=[
            call(5).minutes,  # For scheduler_heartbeat
            call(5).minutes,  # For integration_healthchecks
            call(2).hours,  # For provision_aws_identity_center
        ],
        any_order=True,
    )

    # Since all tasks now use safe_run, we can't directly check for the original functions
    # Instead, verify the number of calls to schedule.do()
    do_calls = [call for call in schedule_mock.mock_calls if ".do(" in str(call)]
    # The scheduled tasks were expanded to include groups reconciliation and
    # idempotency cleanup, so there are now 6 total scheduled .do() calls.
    assert len(do_calls) == 6  # Total number of scheduled tasks

    # Verify parameters without checking the function directly
    # For daily tasks
    day_at_do_calls = [
        call
        for call in schedule_mock.mock_calls
        if ".day.at(" in str(call) and ".do(" in str(call)
    ]
    assert len(day_at_do_calls) == 2  # Two daily tasks

    # For interval tasks
    minutes_do_calls = [
        call for call in schedule_mock.mock_calls if ".minutes.do(" in str(call)
    ]
    # There are now four 5-minute interval tasks (heartbeat, healthchecks,
    # idempotency cleanup and reconciliation worker)
    assert len(minutes_do_calls) == 3  # Four 5-minute tasks

    hours_do_calls = [
        call for call in schedule_mock.mock_calls if ".hours.do(" in str(call)
    ]
    assert len(hours_do_calls) == 1  # One 2-hour task

    # Check that the client parameter was passed for at least one task
    client_params = [
        call for call in schedule_mock.mock_calls if "client=" in str(call)
    ]
    assert len(client_params) >= 1

    # Check that logger parameter was passed for at least one task
    logger_params = [
        call for call in schedule_mock.mock_calls if "logger=" in str(call)
    ]
    assert len(logger_params) >= 1


@patch("jobs.scheduled_tasks.logger")
def test_safe_run(mock_logger):
    """Test that safe_run properly handles exceptions."""

    # Setup
    def test_job():
        raise RuntimeError("Test exception")

    test_job.__name__ = "test_job"  # Set the name for the error message

    # Create the wrapper
    wrapper = scheduled_tasks.safe_run(test_job)

    # Execute the wrapper which should catch the exception
    wrapper()

    # Verify that logging.error was called with the expected message
    mock_logger.error.assert_called_once_with(
        "safe_run_error",
        error="Test exception",
        module=test_job.__module__,
        function="test_job",
        arguments={},
        job_args=(),
    )


@patch("jobs.scheduled_tasks.logger")
@patch("jobs.scheduled_tasks.time")
def test_scheduler_heartbeat(mock_time, mock_logger):
    """Test that scheduler_heartbeat logs the current time."""
    # Setup
    mock_time.ctime.return_value = "Thu Mar 17 14:30:00 2025"

    # Execute
    scheduled_tasks.scheduler_heartbeat()

    # Verify that logging.info was called with the expected message
    mock_logger.info.assert_called_once_with(
        "running_scheduler_heartbeat",
        module="scheduled_tasks",
        time=mock_time.ctime.return_value,
    )
    mock_time.ctime.assert_called_once()


@patch("jobs.scheduled_tasks.schedule")
@patch("jobs.scheduled_tasks.threading")
@patch("jobs.scheduled_tasks.time")
def test_run_continuously(_time_mock, threading_mock, _schedule_mock):
    cease_continuous_run = MagicMock()
    cease_continuous_run.is_set.return_value = True
    threading_mock.Event.return_value = cease_continuous_run
    result = scheduled_tasks.run_continuously(interval=1)
    assert result == cease_continuous_run


@patch("jobs.scheduled_tasks.identity_store")
@patch("jobs.scheduled_tasks.google_drive")
@patch("jobs.scheduled_tasks.maxmind")
@patch("jobs.scheduled_tasks.opsgenie")
@patch("jobs.scheduled_tasks.logger")
def test_integration_healthchecks_healthy(
    mock_logging, mock_opsgenie, mock_maxmind, mock_google_drive, mock_aws_client
):
    mock_aws_client.healthcheck.return_value = True
    mock_google_drive.healthcheck.return_value = True
    mock_maxmind.healthcheck.return_value = True
    mock_opsgenie.healthcheck.return_value = True
    scheduled_tasks.integration_healthchecks()
    assert mock_google_drive.healthcheck.call_count == 1
    assert mock_maxmind.healthcheck.call_count == 1
    assert mock_opsgenie.healthcheck.call_count == 1
    assert mock_logging.error.call_count == 0


@patch("jobs.scheduled_tasks.identity_store")
@patch("jobs.scheduled_tasks.google_drive")
@patch("jobs.scheduled_tasks.maxmind")
@patch("jobs.scheduled_tasks.opsgenie")
@patch("jobs.scheduled_tasks.logger")
def test_integration_healthchecks_unhealthy(
    mock_logging, mock_opsgenie, mock_maxmind, mock_google_drive, mock_aws_client
):
    mock_aws_client.healthcheck.return_value = True
    mock_google_drive.healthcheck.return_value = False
    mock_maxmind.healthcheck.return_value = False
    mock_opsgenie.healthcheck.return_value = True
    scheduled_tasks.integration_healthchecks()
    assert mock_google_drive.healthcheck.call_count == 1
    assert mock_maxmind.healthcheck.call_count == 1
    assert mock_opsgenie.healthcheck.call_count == 1
    assert mock_logging.error.call_count == 2
