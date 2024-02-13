from unittest.mock import MagicMock

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
    pattern = r'^incident-\d{4}-'
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
