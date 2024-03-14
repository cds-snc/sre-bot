from unittest.mock import MagicMock

from integrations.slack import users


def test_get_user_id_from_request_with_user_id():
    body = {"user_id": "U00AAAAAAA0"}
    assert users.get_user_id_from_request(body) == "U00AAAAAAA0"


def test_get_user_id_from_request_with_id():
    body = {"user": {"id": "U00AAAAAAA0"}}
    assert users.get_user_id_from_request(body) == "U00AAAAAAA0"


def test_get_user_id_from_request_without_id():
    body = {"user": "U00AAAAAAA0"}
    assert users.get_user_id_from_request(body) == "U00AAAAAAA0"


def test_get_user_id_from_event_request():
    body = {"event": {"user": "U00AAAAAAA0"}}
    assert users.get_user_id_from_request(body) == "U00AAAAAAA0"


def test_get_user_id_from_invalid_request():
    body = {"invalid": "invalid"}
    assert users.get_user_id_from_request(body) is None


def test_get_user_locale_supported_locale():
    client = MagicMock()
    user_id = MagicMock()
    client.users_info.return_value = {
        "ok": True,
        "user": {"id": "U00AAAAAAA0", "locale": "fr-FR"},
    }
    assert users.get_user_locale(client, user_id) == "fr-FR"


def test_get_user_locale_unsupported_locale():
    client = MagicMock()
    user_id = MagicMock()
    client.users_info.return_value = {
        "ok": True,
        "user": {"id": "U00AAAAAAA0", "locale": "es-ES"},
    }
    assert users.get_user_locale(client, user_id) == "en-US"


def test_get_user_locale_without_locale():
    client = MagicMock()
    user_id = MagicMock()
    client.users_info.return_value = {"ok": False}
    assert users.get_user_locale(client, user_id) == "en-US"


def test_get_user_locale_without_user_id():
    client = MagicMock()
    user_id = None
    assert users.get_user_locale(client, user_id) == "en-US"


def test_replace_user_id_with_valid_handle():
    client = MagicMock()
    client.users_profile_get.return_value = {"profile": {"display_name": "user"}}
    assert (
        users.replace_user_id_with_handle(client, "Hello <@U12345>, how are you?")
        == "Hello @user, how are you?"
    )


def test_replace_user_id_with_no_pattern_in_message():
    client = MagicMock()
    client.users_profile_get.return_value = {"profile": {"display_name": "user"}}
    assert (
        users.replace_user_id_with_handle(client, "Hello user, how are you?")
        == "Hello user, how are you?"
    )


def test_replace_user_id_with_empty_handle():
    client = MagicMock()
    client.users_profile_get.return_value = {"profile": {"display_name": ""}}
    assert (
        users.replace_user_id_with_handle(client, "Hello <@U12345>, how are you?")
        == "Hello @, how are you?"
    )


def test_replace_user_id_with_empty_message():
    client = MagicMock()
    assert users.replace_user_id_with_handle(client, "") == ""


def test_replace_user_id_with_two_users():
    client = MagicMock()

    def users_profile_get(user):
        if user == "U1234":
            return {"profile": {"display_name": "john_doe"}}
        elif user == "U5678":
            return {"profile": {"display_name": "jane_smith"}}

    client.users_profile_get.side_effect = users_profile_get

    message = "Hello, <@U1234> and <@U5678>! Welcome to the team."
    expected_message = "Hello, @john_doe and @jane_smith! Welcome to the team."
    assert users.replace_user_id_with_handle(client, message) == expected_message


def test_replace_user_id_with_multiple_users():
    client = MagicMock()

    def users_profile_get(user):
        if user == "U1234":
            return {"profile": {"display_name": "john_doe"}}
        elif user == "U5678":
            return {"profile": {"display_name": "jane_smith"}}
        elif user == "U9101":
            return {"profile": {"display_name": "joe_smith"}}
        elif user == "U1121":
            return {"profile": {"display_name": "jenn_smith"}}

    client.users_profile_get.side_effect = users_profile_get

    message = "Hello, <@U1234> and <@U5678>! Welcome to the team. Also welcome <@U9101> and <@U1121>."
    expected_message = "Hello, @john_doe and @jane_smith! Welcome to the team. Also welcome @joe_smith and @jenn_smith."
    assert users.replace_user_id_with_handle(client, message) == expected_message
