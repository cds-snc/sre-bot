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
    bound_logger_mock = mock_logger.bind.return_value
    client = MagicMock()
    client.users_list.return_value = {"ok": False, "error": "error"}
    assert users.get_all_users(client) == []
    bound_logger_mock.error.assert_called_once_with(
        "get_all_users_failed", response={"ok": False, "error": "error"}
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


@patch("integrations.slack.users.SlackClientManager")
def test_replace_users_emails_with_mention_success(mock_slack_client_manager):
    mock_client = MagicMock()
    mock_slack_client_manager.get_client.return_value = mock_client
    mock_client.users_lookupByEmail.return_value = {"user": {"id": "U12345"}}

    text = "Please contact john.doe@example.com for more information."
    result = users.replace_users_emails_with_mention(text)

    assert result == "Please contact <@U12345> for more information."
    mock_client.users_lookupByEmail.assert_called_once_with(
        email="john.doe@example.com"
    )


@patch("integrations.slack.users.SlackClientManager")
def test_replace_users_emails_with_mention_multiple_emails(mock_slack_client_manager):
    mock_client = MagicMock()
    mock_slack_client_manager.get_client.return_value = mock_client

    def mock_lookup_by_email(email):
        if email == "john.doe@example.com":
            return {"user": {"id": "U12345"}}
        elif email == "jane.smith@example.com":
            return {"user": {"id": "U67890"}}
        return None

    mock_client.users_lookupByEmail.side_effect = mock_lookup_by_email

    text = "Contact john.doe@example.com or jane.smith@example.com for help."
    result = users.replace_users_emails_with_mention(text)

    assert result == "Contact <@U12345> or <@U67890> for help."
    assert mock_client.users_lookupByEmail.call_count == 2


@patch("integrations.slack.users.SlackClientManager")
def test_replace_users_emails_with_mention_no_user_found(mock_slack_client_manager):
    mock_client = MagicMock()
    mock_slack_client_manager.get_client.return_value = mock_client
    mock_client.users_lookupByEmail.return_value = None

    text = "Please contact unknown@example.com for more information."
    result = users.replace_users_emails_with_mention(text)

    assert result == "Please contact unknown@example.com for more information."
    mock_client.users_lookupByEmail.assert_called_once_with(email="unknown@example.com")


@patch("integrations.slack.users.SlackClientManager")
def test_replace_users_emails_with_mention_no_user_id(mock_slack_client_manager):
    mock_client = MagicMock()
    mock_slack_client_manager.get_client.return_value = mock_client
    mock_client.users_lookupByEmail.return_value = {"user": {}}

    text = "Please contact john.doe@example.com for more information."
    result = users.replace_users_emails_with_mention(text)

    assert result == "Please contact john.doe@example.com for more information."
    mock_client.users_lookupByEmail.assert_called_once_with(
        email="john.doe@example.com"
    )


@patch("integrations.slack.users.SlackClientManager")
def test_replace_users_emails_with_mention_no_client(mock_slack_client_manager):
    mock_slack_client_manager.get_client.return_value = None

    text = "Please contact john.doe@example.com for more information."
    result = users.replace_users_emails_with_mention(text)

    assert result == "Please contact john.doe@example.com for more information."


@patch("integrations.slack.users.SlackClientManager")
def test_replace_users_emails_with_mention_no_emails(mock_slack_client_manager):
    mock_client = MagicMock()
    mock_slack_client_manager.get_client.return_value = mock_client

    text = "This text has no email addresses in it."
    result = users.replace_users_emails_with_mention(text)

    assert result == "This text has no email addresses in it."
    mock_client.users_lookupByEmail.assert_not_called()


@patch("integrations.slack.users.SlackClientManager")
def test_replace_users_emails_with_mention_empty_text(mock_slack_client_manager):
    mock_client = MagicMock()
    mock_slack_client_manager.get_client.return_value = mock_client

    text = ""
    result = users.replace_users_emails_with_mention(text)

    assert result == ""
    mock_client.users_lookupByEmail.assert_not_called()


@patch("integrations.slack.users.replace_users_emails_with_mention")
def test_replace_users_emails_in_dict_string_value(mock_replace_function):
    mock_replace_function.return_value = "replaced text"

    data = "john.doe@example.com"
    result = users.replace_users_emails_in_dict(data)

    assert result == "replaced text"
    mock_replace_function.assert_called_once_with("john.doe@example.com")


@patch("integrations.slack.users.replace_users_emails_with_mention")
def test_replace_users_emails_in_dict_simple_dict(mock_replace_function):
    mock_replace_function.side_effect = lambda x: x.replace(
        "john.doe@example.com", "<@U12345>"
    )

    data = {"message": "Contact john.doe@example.com", "title": "Important"}
    result = users.replace_users_emails_in_dict(data)

    expected = {"message": "Contact <@U12345>", "title": "Important"}
    assert result == expected


@patch("integrations.slack.users.replace_users_emails_with_mention")
def test_replace_users_emails_in_dict_nested_dict(mock_replace_function):
    mock_replace_function.side_effect = lambda x: (
        x.replace("jane@example.com", "<@U67890>") if "jane@example.com" in x else x
    )

    data = {
        "user": {"contact": "jane@example.com", "name": "Jane"},
        "metadata": {"created_by": "system"},
    }
    result = users.replace_users_emails_in_dict(data)

    expected = {
        "user": {"contact": "<@U67890>", "name": "Jane"},
        "metadata": {"created_by": "system"},
    }
    assert result == expected


@patch("integrations.slack.users.replace_users_emails_with_mention")
def test_replace_users_emails_in_dict_list_of_strings(mock_replace_function):
    mock_replace_function.side_effect = lambda x: (
        x.replace("test@example.com", "<@U11111>") if "test@example.com" in x else x
    )

    data = ["Contact test@example.com", "No email here", "Another message"]
    result = users.replace_users_emails_in_dict(data)

    expected = ["Contact <@U11111>", "No email here", "Another message"]
    assert result == expected


@patch("integrations.slack.users.replace_users_emails_with_mention")
def test_replace_users_emails_in_dict_list_of_dicts(mock_replace_function):
    mock_replace_function.side_effect = lambda x: (
        x.replace("admin@example.com", "<@U22222>") if "admin@example.com" in x else x
    )

    data = [
        {"message": "Contact admin@example.com", "priority": "high"},
        {"message": "No email", "priority": "low"},
    ]
    result = users.replace_users_emails_in_dict(data)

    expected = [
        {"message": "Contact <@U22222>", "priority": "high"},
        {"message": "No email", "priority": "low"},
    ]
    assert result == expected


@patch("integrations.slack.users.replace_users_emails_with_mention")
def test_replace_users_emails_in_dict_mixed_types(mock_replace_function):
    def mock_replacement(x):
        if "user@example.com" in x:
            return x.replace("user@example.com", "<@U33333>")
        return x

    mock_replace_function.side_effect = mock_replacement

    data = {
        "text": "Contact user@example.com",
        "number": 42,
        "boolean": True,
        "null_value": None,
        "list": ["user@example.com", 123, False],
    }
    result = users.replace_users_emails_in_dict(data)

    expected = {
        "text": "Contact <@U33333>",
        "number": 42,
        "boolean": True,
        "null_value": None,
        "list": ["<@U33333>", 123, False],
    }
    assert result == expected


@patch("integrations.slack.users.replace_users_emails_with_mention")
def test_replace_users_emails_in_dict_non_string_non_dict_non_list(
    mock_replace_function,
):
    data = 42
    result = users.replace_users_emails_in_dict(data)

    assert result == 42
    mock_replace_function.assert_not_called()
