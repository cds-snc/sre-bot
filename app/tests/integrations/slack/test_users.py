import time
from unittest.mock import MagicMock, patch

import pytest
from slack_sdk import WebClient

from integrations.slack import users


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
    assert users.get_all_users(client) == [{"id": "U00AAAAAAA0", "name": "user1", "deleted": False, "is_bot": False}]


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
    bound_logger_mock.error.assert_called_once_with("get_all_users_failed", response={"ok": False, "error": "error"})


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
    assert users.replace_user_id_with_handle(client, "Hello <@U12345>, how are you?") == "Hello @user, how are you?"


def test_replace_user_id_with_no_pattern_in_message():
    client = MagicMock()
    client.users_profile_get.return_value = {"profile": {"display_name": "user"}}
    assert users.replace_user_id_with_handle(client, "Hello user, how are you?") == "Hello user, how are you?"


def test_replace_user_id_with_empty_handle():
    client = MagicMock()
    client.users_profile_get.return_value = {"profile": {"display_name": ""}}
    assert users.replace_user_id_with_handle(client, "Hello <@U12345>, how are you?") == "Hello @, how are you?"


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

    assert users.get_user_email_from_handle(client, "@user_name1") == "user_email1@test.com"
    assert users.get_user_email_from_handle(client, "@user_name2") == "user_email2@test.com"
    assert users.get_user_email_from_handle(client, "@unknown_name") is None


@patch("integrations.slack.users.get_slack_web_client")
def test_replace_users_emails_with_mention_success(mock_get_slack_web_client):
    mock_client = MagicMock()
    mock_get_slack_web_client.return_value = mock_client
    mock_client.users_lookupByEmail.return_value = {"user": {"id": "U12345"}}

    text = "Please contact john.doe@example.com for more information."
    result = users.replace_users_emails_with_mention(text)

    assert result == "Please contact <@U12345> for more information."
    mock_client.users_lookupByEmail.assert_called_once_with(email="john.doe@example.com")


@patch("integrations.slack.users.get_slack_web_client")
def test_replace_users_emails_with_mention_multiple_emails(mock_get_slack_web_client):
    mock_client = MagicMock()
    mock_get_slack_web_client.return_value = mock_client

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


@patch("integrations.slack.users.get_slack_web_client")
def test_replace_users_emails_with_mention_no_user_found(mock_get_slack_web_client):
    mock_client = MagicMock()
    mock_get_slack_web_client.return_value = mock_client
    mock_client.users_lookupByEmail.return_value = None

    text = "Please contact unknown@example.com for more information."
    result = users.replace_users_emails_with_mention(text)

    assert result == "Please contact unknown@example.com for more information."
    mock_client.users_lookupByEmail.assert_called_once_with(email="unknown@example.com")


@patch("integrations.slack.users.get_slack_web_client")
def test_replace_users_emails_with_mention_no_user_id(mock_get_slack_web_client):
    mock_client = MagicMock()
    mock_get_slack_web_client.return_value = mock_client
    mock_client.users_lookupByEmail.return_value = {"user": {}}

    text = "Please contact john.doe@example.com for more information."
    result = users.replace_users_emails_with_mention(text)

    assert result == "Please contact john.doe@example.com for more information."
    mock_client.users_lookupByEmail.assert_called_once_with(email="john.doe@example.com")


@patch("integrations.slack.users.get_slack_web_client")
def test_replace_users_emails_with_mention_no_client(mock_get_slack_web_client):
    mock_get_slack_web_client.return_value = None

    text = "Please contact john.doe@example.com for more information."
    result = users.replace_users_emails_with_mention(text)

    assert result == "Please contact john.doe@example.com for more information."


@patch("integrations.slack.users.get_slack_web_client")
def test_replace_users_emails_with_mention_no_emails(mock_get_slack_web_client):
    mock_client = MagicMock()
    mock_get_slack_web_client.return_value = mock_client

    text = "This text has no email addresses in it."
    result = users.replace_users_emails_with_mention(text)

    assert result == "This text has no email addresses in it."
    mock_client.users_lookupByEmail.assert_not_called()


@patch("integrations.slack.users.get_slack_web_client")
def test_replace_users_emails_with_mention_empty_text(mock_get_slack_web_client):
    mock_client = MagicMock()
    mock_get_slack_web_client.return_value = mock_client

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
    mock_replace_function.side_effect = lambda x: x.replace("john.doe@example.com", "<@U12345>")

    data = {"message": "Contact john.doe@example.com", "title": "Important"}
    result = users.replace_users_emails_in_dict(data)

    expected = {"message": "Contact <@U12345>", "title": "Important"}
    assert result == expected


@patch("integrations.slack.users.replace_users_emails_with_mention")
def test_replace_users_emails_in_dict_nested_dict(mock_replace_function):
    mock_replace_function.side_effect = lambda x: x.replace("jane@example.com", "<@U67890>") if "jane@example.com" in x else x

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
    mock_replace_function.side_effect = lambda x: x.replace("test@example.com", "<@U11111>") if "test@example.com" in x else x

    data = ["Contact test@example.com", "No email here", "Another message"]
    result = users.replace_users_emails_in_dict(data)

    expected = ["Contact <@U11111>", "No email here", "Another message"]
    assert result == expected


@patch("integrations.slack.users.replace_users_emails_with_mention")
def test_replace_users_emails_in_dict_list_of_dicts(mock_replace_function):
    mock_replace_function.side_effect = lambda x: x.replace("admin@example.com", "<@U22222>") if "admin@example.com" in x else x

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


_BODY_CAP_BYTES = 262_144
_LINEAR_TIME_BUDGET_SECONDS = 0.5


@pytest.mark.parametrize(
    "adversarial_text",
    [
        "a" * _BODY_CAP_BYTES,
        "a" * (_BODY_CAP_BYTES // 2) + "@" + "a" * (_BODY_CAP_BYTES // 2),
        "x@" + "a." * (_BODY_CAP_BYTES // 2),
        "a@" * (_BODY_CAP_BYTES // 2),
        "." * _BODY_CAP_BYTES,
    ],
    ids=["no-at", "at-without-dot", "dotted-domain-without-tld", "repeated-at", "dot-run"],
)
@patch("integrations.slack.users.get_slack_web_client")
def test_replace_users_emails_with_mention_scans_a_body_cap_sized_text_in_linear_time(
    mock_get_slack_web_client, adversarial_text
):
    """Text as large as the webhook body cap, shaped to make a backtracking pattern retry, is scanned well under the budget.

    The Slack client is a MagicMock, so the time measured is the matching alone; none of
    these shapes holds an address, so no lookup is made and the text comes back unchanged.
    A quadratic matcher takes minutes on these inputs, so the budget separates the two.
    """
    mock_client = MagicMock()
    mock_get_slack_web_client.return_value = mock_client

    started = time.perf_counter()
    result = users.replace_users_emails_with_mention(adversarial_text)
    elapsed = time.perf_counter() - started

    assert elapsed < _LINEAR_TIME_BUDGET_SECONDS
    assert result == adversarial_text
    mock_client.users_lookupByEmail.assert_not_called()


@pytest.mark.parametrize(
    ("text", "addresses"),
    [
        ("Reach john.doe@example.com today", ["john.doe@example.com"]),
        ("plus first+tag@example.com", ["first+tag@example.com"]),
        ("percent ops%team@example.com", ["ops%team@example.com"]),
        ("hyphen a_b-c@sub-domain.example.co.uk!", ["a_b-c@sub-domain.example.co.uk"]),
        ("two a@x.org,b@y.ca", ["a@x.org", "b@y.ca"]),
        ("link <mailto:a@x.org|a@x.org>", ["a@x.org", "a@x.org"]),
        ("trailing dot a@x.org.", ["a@x.org"]),
    ],
    ids=["dotted-local", "plus", "percent", "hyphenated-multi-label", "two-addresses", "mailto-link", "trailing-dot"],
)
@patch("integrations.slack.users.get_slack_web_client")
def test_replace_users_emails_with_mention_looks_up_each_address_and_replaces_it(mock_get_slack_web_client, text, addresses):
    """Each address in the text is looked up in order and every occurrence becomes the user's mention.

    The Slack client is a MagicMock answering every lookup with one user id, so the
    lookups made and the rewritten text show exactly which substrings were taken as addresses.
    """
    mock_client = MagicMock()
    mock_get_slack_web_client.return_value = mock_client
    mock_client.users_lookupByEmail.return_value = {"user": {"id": "U1"}}

    result = users.replace_users_emails_with_mention(text)

    assert [call.kwargs["email"] for call in mock_client.users_lookupByEmail.call_args_list] == addresses
    expected = text
    for address in addresses:
        expected = expected.replace(address, "<@U1>")
    assert result == expected


@pytest.mark.parametrize(
    "text",
    ["short tld x@y.c", "no local part @x.com", "no domain dot a@b", "empty label user@.com"],
)
@patch("integrations.slack.users.get_slack_web_client")
def test_replace_users_emails_with_mention_leaves_non_addresses_untouched(mock_get_slack_web_client, text):
    """Strings that only resemble an address are not looked up and the text comes back unchanged.

    The Slack client is a MagicMock; asserting it was never called proves nothing was
    taken as an address.
    """
    mock_client = MagicMock()
    mock_get_slack_web_client.return_value = mock_client

    result = users.replace_users_emails_with_mention(text)

    assert result == text
    mock_client.users_lookupByEmail.assert_not_called()
