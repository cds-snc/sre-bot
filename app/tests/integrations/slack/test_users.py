from unittest.mock import MagicMock, patch

from integrations.slack import users
from slack_sdk import WebClient


def test_get_all_users():
    client = MagicMock()
    client.users_list.return_value = {
        "ok": True,
        "members": [
            {"id": "U00AAAAAAA0", "name": "user1", "deleted": False, "is_bot": False},
            {"id": "U00AAAAAAA1", "name": "user2", "deleted": True, "is_bot": False},
            {"id": "U00AAAAAAA2", "name": "user3", "deleted": False, "is_bot": True},
        ],
    }
    assert users.get_all_users(client) == [
        {"id": "U00AAAAAAA0", "name": "user1", "deleted": False, "is_bot": False}
    ]


def test_get_all_users_with_pagination():
    client = MagicMock()
    client.users_list.side_effect = [
        {
            "ok": True,
            "members": [
                {
                    "id": "U00AAAAAAA0",
                    "name": "user1",
                    "deleted": False,
                    "is_bot": False,
                },
                {
                    "id": "U00AAAAAAA1",
                    "name": "user2",
                    "deleted": False,
                    "is_bot": False,
                },
            ],
            "response_metadata": {"next_cursor": "cursor"},
        },
        {
            "ok": True,
            "members": [
                {
                    "id": "U00AAAAAAA2",
                    "name": "user3",
                    "deleted": False,
                    "is_bot": False,
                }
            ],
            "response_metadata": {
                "next_cursor": "",
            },
        },
    ]
    assert users.get_all_users(client) == [
        {"id": "U00AAAAAAA0", "name": "user1", "deleted": False, "is_bot": False},
        {"id": "U00AAAAAAA1", "name": "user2", "deleted": False, "is_bot": False},
        {"id": "U00AAAAAAA2", "name": "user3", "deleted": False, "is_bot": False},
    ]

    assert client.users_list.call_count == 2


def test_get_all_users_with_deleted():
    client = MagicMock()
    client.users_list.return_value = {
        "ok": True,
        "members": [
            {"id": "U00AAAAAAA0", "name": "user1", "deleted": False, "is_bot": False},
            {"id": "U00AAAAAAA1", "name": "user2", "deleted": True, "is_bot": False},
            {"id": "U00AAAAAAA2", "name": "user3", "deleted": False, "is_bot": True},
        ],
    }
    assert users.get_all_users(client, deleted=True) == [
        {"id": "U00AAAAAAA0", "name": "user1", "deleted": False, "is_bot": False},
        {"id": "U00AAAAAAA1", "name": "user2", "deleted": True, "is_bot": False},
    ]


def test_get_all_users_with_bot():
    client = MagicMock()
    client.users_list.return_value = {
        "ok": True,
        "members": [
            {"id": "U00AAAAAAA0", "name": "user1", "deleted": False, "is_bot": False},
            {"id": "U00AAAAAAA1", "name": "user2", "deleted": True, "is_bot": False},
            {"id": "U00AAAAAAA2", "name": "user3", "deleted": False, "is_bot": True},
        ],
    }
    assert users.get_all_users(client, is_bot=True) == [
        {"id": "U00AAAAAAA0", "name": "user1", "deleted": False, "is_bot": False},
        {"id": "U00AAAAAAA2", "name": "user3", "deleted": False, "is_bot": True},
    ]


@patch("integrations.slack.users.logger")
def test_get_all_users_with_error(mock_logger):
    client = MagicMock()
    client.users_list.return_value = {"ok": False, "error": "error"}
    assert users.get_all_users(client) == []
    mock_logger.error.assert_called_once_with(
        "get_all_users_failed", extra={"response": {"ok": False, "error": "error"}}
    )


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


@patch("integrations.slack.users.get_all_users")
def test_get_user_email(mock_get_all_users):
    # Mock the WebClient

    mock_get_all_users.return_value = [
        {"id": "U1234", "name": "user_name1", "profile": {"email": "email1@test.com"}},
        {"id": "U5678", "name": "user_name2", "profile": {"email": "email2@test.com"}},
    ]
    client = MagicMock(spec=WebClient)

    # Test when the user ID is found in the request body and the users_info call is successful
    client.users_info.return_value = {
        "ok": True,
        "user": {"profile": {"email": "test@example.com"}},
    }
    body = {"user_id": "U1234"}
    assert users.get_user_email_from_body(client, body) == "test@example.com"

    # Test when the user ID is not found in the request body
    body = {}
    assert users.get_user_email_from_body(client, body) is None

    # Test when the users_info call is not successful
    client.users_info.return_value = {"ok": False}
    body = {"user_id": "U1234"}
    assert users.get_user_email_from_body(client, body) is None


@patch("integrations.slack.users.get_all_users")
def test_get_user_email_from_handle(mock_get_all_users):

    client = MagicMock(spec=WebClient)
    mock_get_all_users.return_value = [
        {
            "id": "U1234",
            "name": "user_name1",
            "profile": {"email": "user_email1@test.com"},
        },
        {
            "id": "U5678",
            "name": "user_name2",
            "profile": {"email": "user_email2@test.com"},
        },
    ]

    client.users_info.side_effect = lambda user: {
        "U1234": {"ok": True, "user": {"profile": {"email": "user_email1@test.com"}}},
        "U5678": {"ok": True, "user": {"profile": {"email": "user_email2@test.com"}}},
    }.get(user, {})

    assert (
        users.get_user_email_from_handle(client, "@user_name1")
        == "user_email1@test.com"
    )
    assert (
        users.get_user_email_from_handle(client, "@user_name2")
        == "user_email2@test.com"
    )
    assert users.get_user_email_from_handle(client, "@unknown_name") is None
