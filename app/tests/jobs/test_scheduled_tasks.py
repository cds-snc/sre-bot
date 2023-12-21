from jobs import scheduled_tasks

from unittest.mock import call, MagicMock, patch


@patch("jobs.scheduled_tasks.schedule")
def test_init(schedule_mock):
    bot = MagicMock()
    scheduled_tasks.init(bot)
    schedule_mock.every().day.at.assert_called_once_with("16:00")
    schedule_mock.every().day.at.return_value.do.assert_called_once_with(
        scheduled_tasks.notify_stale_incident_channels, client=bot.client
    )
    schedule_mock.every().minutes.do.assert_has_calls(
        [
            call(scheduled_tasks.scheduler_heartbeat),
            call(scheduled_tasks.client_vpn_turn_off),
        ]
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
