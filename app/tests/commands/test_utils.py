from commands import utils
from integrations.slack import users as slack_users
from unittest.mock import MagicMock, patch


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
    assert slack_users.get_user_locale(client, user_id) == "fr-FR"


def test_get_user_locale_unsupported_locale():
    client = MagicMock()
    user_id = MagicMock()
    client.users_info.return_value = {
        "ok": True,
        "user": {"id": "U00AAAAAAA0", "locale": "es-ES"},
    }
    assert slack_users.get_user_locale(client, user_id) == "en-US"


def test_get_user_locale_without_locale():
    client = MagicMock()
    user_id = MagicMock()
    client.users_info.return_value = {"ok": False}
    assert slack_users.get_user_locale(client, user_id) == "en-US"


def test_basic_functionality_rearrange_by_datetime_ascending():
    input_text = "2024-01-01 10:00:00 ET Message A\n" "2024-01-02 11:00:00 ET Message B"
    expected_output = (
        "2024-01-01 10:00:00 ET Message A\n" "2024-01-02 11:00:00 ET Message B"
    )
    assert utils.rearrange_by_datetime_ascending(input_text) == expected_output


def test_multiline_entries_rearrange_by_datetime_ascending():
    input_text = (
        "2024-01-01 10:00:00 ET Message A\nContinued\n"
        "2024-01-02 11:00:00 ET Message B"
    )
    expected_output = (
        "2024-01-01 10:00:00 ET Message A\nContinued\n"
        "2024-01-02 11:00:00 ET Message B"
    )
    assert utils.rearrange_by_datetime_ascending(input_text) == expected_output


def test_entries_out_of_order_rearrange_by_datetime_ascending():
    input_text = "2024-01-02 11:00:00 ET Message B\n" "2024-01-01 10:00:00 ET Message A"
    expected_output = (
        "2024-01-01 10:00:00 ET Message A\n" "2024-01-02 11:00:00 ET Message B"
    )
    assert utils.rearrange_by_datetime_ascending(input_text) == expected_output


def test_invalid_entries_rearrange_by_datetime_ascending():
    input_text = "Invalid Entry\n" "2024-01-01 10:00:00 ET Message A"
    expected_output = "2024-01-01 10:00:00 ET Message A"
    assert utils.rearrange_by_datetime_ascending(input_text) == expected_output


def test_empty_input_rearrange_by_datetime_ascending():
    assert utils.rearrange_by_datetime_ascending("") == ""


def test_no_datetime_entries_rearrange_by_datetime_ascending():
    input_text = "Message without datetime\nAnother message"
    assert utils.rearrange_by_datetime_ascending(input_text) == ""


def test_convert_epoch_to_datetime_est_known_epoch_time():
    # Example: 0 epoch time corresponds to 1969-12-31 19:00:00 EST
    assert utils.convert_epoch_to_datetime_est(0) == "1969-12-31 19:00:00 ET"


def test_convert_epoch_to_datetime_est_daylight_saving_time_change():
    # Test with an epoch time known to fall in DST transition
    # For example, 1583652000 corresponds to 2020-03-08 03:20:00 EST
    assert utils.convert_epoch_to_datetime_est(1583652000) == "2020-03-08 03:20:00 ET"


def test_convert_epoch_to_datetime_est_current_epoch_time():
    time = MagicMock()
    time.return_value = 1609459200
    current_est = utils.convert_epoch_to_datetime_est(time)
    assert current_est == "1969-12-31 19:00:01 ET"


def test_convert_epoch_to_datetime_est_edge_cases():
    # Test with the epoch time at 0
    assert utils.convert_epoch_to_datetime_est(0) == "1969-12-31 19:00:00 ET"
    # Test with a very large epoch time, for example
    assert utils.convert_epoch_to_datetime_est(32503680000) == "2999-12-31 19:00:00 ET"


def test_replace_user_id_with_valid_handle():
    assert (
        utils.replace_user_id_with_handle("@user", "Hello <@U12345>, how are you?")
        == "Hello @user, how are you?"
    )


def test_replace_user_id_with_no_pattern_in_message():
    assert (
        utils.replace_user_id_with_handle("@user", "Hello user, how are you?")
        == "Hello user, how are you?"
    )


def test_replace_user_id_with_empty_handle():
    assert (
        utils.replace_user_id_with_handle("", "Hello <@U12345>, how are you?") is None
    )


def test_replace_user_id_with_empty_message():
    assert utils.replace_user_id_with_handle("@user", "") is None


def test_replace_user_id_with_none_handle():
    assert (
        utils.replace_user_id_with_handle(None, "Hello <@U12345>, how are you?") is None
    )


def test_replace_user_id_with_none_message():
    assert utils.replace_user_id_with_handle("@user", None) is None


def test_replace_multiple_user_ids_in_message():
    assert (
        utils.replace_user_id_with_handle("@user", "Hi <@U12345>, meet <@U67890>")
        == "Hi @user, meet @user"
    )
