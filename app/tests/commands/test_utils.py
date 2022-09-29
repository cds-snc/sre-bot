from commands import utils
from datetime import timedelta
from unittest.mock import ANY, MagicMock, patch


def test_get_incident_channels():
    client = MagicMock()
    client.conversations_list.return_value = {
        "ok": True,
        "channels": [
            {
                "name": "channel_name",
            },
            {
                "name": "incident-2022-channel",
            },
        ],
    }
    assert utils.get_incident_channels(client) == [
        {
            "name": "incident-2022-channel",
        },
    ]


def test_get_messages_in_time_period():
    client = MagicMock()
    client.conversations_history.return_value = {
        "ok": True,
        "messages": [
            {
                "message": "message",
            },
            {
                "message": "message",
                "team": "team",
            },
        ],
    }
    assert utils.get_messages_in_time_period(
        client, "channel_id", timedelta(days=1)
    ) == [
        {
            "message": "message",
            "team": "team",
        }
    ]
    client.conversations_join.assert_called_with(channel="channel_id")
    client.conversations_history.assert_called_with(
        channel="channel_id", oldest=ANY, limit=10
    )


def test_get_messages_in_time_period_with_error():
    client = MagicMock()
    client.conversations_history.return_value = {"ok": False}
    assert (
        utils.get_messages_in_time_period(client, "channel_id", timedelta(days=1)) == []
    )


@patch("commands.utils.get_incident_channels")
@patch("commands.utils.get_messages_in_time_period")
def test_get_stale_channels(
    get_messages_in_time_period_mock, get_incident_channels_mock
):
    client = MagicMock()
    get_incident_channels_mock.return_value = [
        {"id": "id", "name": "incident-2022-channel", "created": 0},
    ]
    get_messages_in_time_period_mock.return_value = []
    assert utils.get_stale_channels(client) == [
        {"id": "id", "name": "incident-2022-channel", "created": 0}
    ]


def test_log_ops_message():
    client = MagicMock()
    msg = "foo bar baz"
    utils.log_ops_message(client, msg)
    client.chat_postMessage.assert_called_with(
        channel="C0388M21LKZ", text=msg, as_user=True
    )


@patch("commands.utils.send_event")
def test_log_to_sentinel(send_event_mock):
    utils.log_to_sentinel("foo", {"bar": "baz"})
    send_event_mock.assert_called_with({"event": "foo", "message": {"bar": "baz"}})


@patch("commands.utils.send_event")
@patch("commands.utils.logging")
def test_log_to_sentinel_logs_error(logging_mock, send_event_mock):
    send_event_mock.return_value = False
    utils.log_to_sentinel("foo", {"bar": "baz"})
    send_event_mock.assert_called_with({"event": "foo", "message": {"bar": "baz"}})
    logging_mock.error.assert_called_with(
        "Sentinel event failed: {'event': 'foo', 'message': {'bar': 'baz'}}"
    )


def test_parse_command_empty_string():
    assert utils.parse_command("") == []


def test_parse_command_no_args():
    assert utils.parse_command("sre") == ["sre"]


def test_parse_command_one_arg():
    assert utils.parse_command("sre foo") == ["sre", "foo"]


def test_parse_command_two_args():
    assert utils.parse_command("sre foo bar") == ["sre", "foo", "bar"]


def test_parse_command_with_quotes():
    assert utils.parse_command('sre "foo bar baz"') == ["sre", "foo bar baz"]
