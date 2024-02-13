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
