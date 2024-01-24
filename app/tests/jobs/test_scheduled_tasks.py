from jobs import scheduled_tasks

from unittest.mock import MagicMock, patch


@patch("jobs.scheduled_tasks.schedule")
def test_init(schedule_mock):
    bot = MagicMock()
    scheduled_tasks.init(bot)
    schedule_mock.every().day.at.assert_called_once_with("16:00")
    schedule_mock.every().day.at.return_value.do.assert_called_once_with(
        scheduled_tasks.notify_stale_incident_channels, client=bot.client
    )


@patch("jobs.scheduled_tasks.schedule")
@patch("jobs.scheduled_tasks.threading")
@patch("jobs.scheduled_tasks.time")
def test_run_continuously(time_mock, threading_mock, schedule_mock):
    cease_continuous_run = MagicMock()
    cease_continuous_run.is_set.return_value = True
    threading_mock.Event.return_value = cease_continuous_run
    result = scheduled_tasks.run_continuously(interval=1)
    assert result == cease_continuous_run


@patch("jobs.scheduled_tasks.opsgenie")
@patch("jobs.scheduled_tasks.logging")
def test_integration_healthchecks_healthy(mock_logging, mock_opsgenie):
    mock_opsgenie.healthcheck.return_value = True
    scheduled_tasks.integration_healthchecks()
    assert mock_opsgenie.healthcheck.call_count == 1
    assert mock_logging.error.call_count == 0


@patch("jobs.scheduled_tasks.opsgenie")
@patch("jobs.scheduled_tasks.logging")
def test_integration_healthchecks_unhealthy(mock_logging, mock_opsgenie):
    mock_opsgenie.healthcheck.return_value = False
    mock_opsgenie.healthcheck.__name__ = "test_integration"
    scheduled_tasks.integration_healthchecks()
    assert mock_opsgenie.healthcheck.call_count == 1
    assert mock_logging.error.call_count == 1
