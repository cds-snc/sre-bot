from datetime import timedelta
from unittest.mock import MagicMock, patch, ANY

from integrations.slack import channels


def test_get_channels_without_pattern():
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
        "response_metadata": {"next_cursor": ""},
    }
    assert channels.get_channels(client) == [
        {
            "name": "channel_name",
        },
        {
            "name": "incident-2022-channel",
        },
    ]


def test_get_channels_without_pattern_with_multiple_pages():
    client = MagicMock()

    # Define mock responses
    mock_response_page_1 = {
        "ok": True,
        "channels": [
            {"name": "incident-2021-alpha"},
            {"name": "general"},
            {"name": "incident-2020-beta"},
        ],
        "response_metadata": {"next_cursor": "cursor123"},
    }
    mock_response_page_2 = {
        "ok": True,
        "channels": [{"name": "random"}, {"name": "incident-2022-gamma"}],
        "response_metadata": {"next_cursor": ""},
    }

    # Set the side_effect of the conversations_list method
    client.conversations_list.side_effect = [mock_response_page_1, mock_response_page_2]

    # Call the function
    result = channels.get_channels(client)

    # Verify results
    expected_channels = [
        {"name": "incident-2021-alpha"},
        {"name": "general"},
        {"name": "incident-2020-beta"},
        {"name": "random"},
        {"name": "incident-2022-gamma"},
    ]
    assert result == expected_channels


def test_get_channels_with_pattern():
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
        "response_metadata": {"next_cursor": ""},
    }
    pattern = r"^incident-\d{4}-"
    assert channels.get_channels(client, pattern) == [
        {
            "name": "incident-2022-channel",
        },
    ]


# Test get_incident_channels with multiple pages of results
def test_get_channels_with_pattern_with_multiple_pages():
    client = MagicMock()

    # Define mock responses
    mock_response_page_1 = {
        "ok": True,
        "channels": [
            {"name": "incident-2021-alpha"},
            {"name": "general"},
            {"name": "incident-2020-beta"},
        ],
        "response_metadata": {"next_cursor": "cursor123"},
    }
    mock_response_page_2 = {
        "ok": True,
        "channels": [{"name": "random"}, {"name": "incident-2022-gamma"}],
        "response_metadata": {"next_cursor": ""},
    }

    # Set the side_effect of the conversations_list method
    client.conversations_list.side_effect = [mock_response_page_1, mock_response_page_2]

    # Call the function
    result = channels.get_channels(client, "incident-20")

    # Verify results
    expected_channels = [
        {"name": "incident-2021-alpha"},
        {"name": "incident-2020-beta"},
        {"name": "incident-2022-gamma"},
    ]
    assert result == expected_channels


def test_get_channels_with_error_returns_empty_list():
    client = MagicMock()
    client.conversations_list.return_value = {"ok": False}
    assert channels.get_channels(client) == []


@patch("integrations.slack.channels.get_channels")
@patch("integrations.slack.channels.get_messages_in_time_period")
def test_get_stale_channels_without_pattern_calls_get_channels_with_client_only(
    get_messages_in_time_period_mock, get_channels_mock
):
    client = MagicMock()
    get_channels_mock.return_value = [
        {"id": "id", "name": "incident-2022-channel", "created": 0},
    ]
    get_messages_in_time_period_mock.return_value = []
    assert channels.get_stale_channels(client) == [
        {"id": "id", "name": "incident-2022-channel", "created": 0}
    ]
    get_channels_mock.assert_called_once_with(client, pattern=None)


@patch("integrations.slack.channels.get_channels")
@patch("integrations.slack.channels.get_messages_in_time_period")
def test_get_stale_channels_with_pattern_calls_get_channels_with_pattern(
    get_messages_in_time_period_mock, get_channels_mock
):
    client = MagicMock()
    pattern = r"^incident-\d{4}-"
    get_channels_mock.return_value = [
        {"id": "id", "name": "incident-2022-channel", "created": 0},
    ]
    get_messages_in_time_period_mock.return_value = []
    assert channels.get_stale_channels(client, pattern) == [
        {"id": "id", "name": "incident-2022-channel", "created": 0}
    ]
    get_channels_mock.assert_called_once_with(client, pattern=pattern)


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
    assert channels.get_messages_in_time_period(
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
        channels.get_messages_in_time_period(client, "channel_id", timedelta(days=1)) == []
    )