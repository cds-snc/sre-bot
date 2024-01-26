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
        "response_metadata": {"next_cursor": ""},
    }
    assert utils.get_incident_channels(client) == [
        {
            "name": "incident-2022-channel",
        },
    ]


# Test get_incident_channels with multiple pages of results
def test_get_incident_channels_with_multiple_pages():
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
    result = utils.get_incident_channels(client)

    # Verify results
    expected_channels = [
        {"name": "incident-2021-alpha"},
        {"name": "incident-2020-beta"},
        {"name": "incident-2022-gamma"},
    ]
    assert result == expected_channels


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


def test_get_user_locale_supported_locale():
    client = MagicMock()
    user_id = MagicMock()
    client.users_info.return_value = {
        "ok": True,
        "user": {"id": "U00AAAAAAA0", "locale": "fr-FR"},
    }
    assert utils.get_user_locale(user_id, client) == "fr-FR"


def test_get_user_locale_unsupported_locale():
    client = MagicMock()
    user_id = MagicMock()
    client.users_info.return_value = {
        "ok": True,
        "user": {"id": "U00AAAAAAA0", "locale": "es-ES"},
    }
    assert utils.get_user_locale(user_id, client) == "en-US"


def test_get_user_locale_without_locale():
    client = MagicMock()
    user_id = MagicMock()
    client.users_info.return_value = {"ok": False}
    assert utils.get_user_locale(user_id, client) == "en-US"


def test_basic_functionality_rearrange_by_datetime_ascending():
    input_text = (
        "2024-01-01 10:00:00 EST Message A\n" "2024-01-02 11:00:00 EST Message B"
    )
    expected_output = (
        "2024-01-01 10:00:00 EST Message A\n" "2024-01-02 11:00:00 EST Message B"
    )
    assert utils.rearrange_by_datetime_ascending(input_text) == expected_output


def test_multiline_entries_rearrange_by_datetime_ascending():
    input_text = (
        "2024-01-01 10:00:00 EST Message A\nContinued\n"
        "2024-01-02 11:00:00 EST Message B"
    )
    expected_output = (
        "2024-01-01 10:00:00 EST Message A\nContinued\n"
        "2024-01-02 11:00:00 EST Message B"
    )
    assert utils.rearrange_by_datetime_ascending(input_text) == expected_output


def test_entries_out_of_order_rearrange_by_datetime_ascending():
    input_text = (
        "2024-01-02 11:00:00 EST Message B\n" "2024-01-01 10:00:00 EST Message A"
    )
    expected_output = (
        "2024-01-01 10:00:00 EST Message A\n" "2024-01-02 11:00:00 EST Message B"
    )
    assert utils.rearrange_by_datetime_ascending(input_text) == expected_output


def test_invalid_entries_rearrange_by_datetime_ascending():
    input_text = "Invalid Entry\n" "2024-01-01 10:00:00 EST Message A"
    expected_output = "2024-01-01 10:00:00 EST Message A"
    assert utils.rearrange_by_datetime_ascending(input_text) == expected_output


def test_empty_input_rearrange_by_datetime_ascending():
    assert utils.rearrange_by_datetime_ascending("") == ""


def test_no_datetime_entries_rearrange_by_datetime_ascending():
    input_text = "Message without datetime\nAnother message"
    assert utils.rearrange_by_datetime_ascending(input_text) == ""


def test_known_epoch_time():
    # Example: 0 epoch time corresponds to 1969-12-31 19:00:00 EST
    assert utils.convert_epoch_to_datetime_est(0) == "1969-12-31 19:00:00 EST"


def test_daylight_saving_time_change():
    # Test with an epoch time known to fall in DST transition
    # For example, 1583652000 corresponds to 2020-03-08 03:20:00 EST
    assert utils.convert_epoch_to_datetime_est(1583652000) == "2020-03-08 03:20:00 EST"


def test_current_epoch_time():
    time = MagicMock()
    time.return_value = 1609459200
    current_est = utils.convert_epoch_to_datetime_est(time)
    assert current_est == "1969-12-31 19:00:01 EST"


def test_edge_cases():
    # Test with the epoch time at 0
    assert utils.convert_epoch_to_datetime_est(0) == "1969-12-31 19:00:00 EST"
    # Test with a very large epoch time, for example
    assert utils.convert_epoch_to_datetime_est(32503680000) == "2999-12-31 19:00:00 EST"


def test_valid_google_docs_url():
    url = "https://docs.google.com/document/d/1aBcD_efGHI/edit"
    assert utils.extract_google_doc_id(url) == "1aBcD_efGHI"


def test_google_docs_url_with_parameters():
    url = "https://docs.google.com/document/d/1aBcD_efGHI/edit?usp=sharing"
    assert utils.extract_google_doc_id(url) == "1aBcD_efGHI"


def test_non_google_docs_url():
    url = "https://www.example.com/page/d/1aBcD_efGHI/other"
    assert utils.extract_google_doc_id(url) is None


def test_invalid_url_format():
    url = "https://docs.google.com/document/1aBcD_efGHI"
    assert utils.extract_google_doc_id(url) is None


def test_empty_string():
    assert utils.extract_google_doc_id("") is None


def test_none_input():
    assert utils.extract_google_doc_id(None) is None
