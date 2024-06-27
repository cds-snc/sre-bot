import pytest
from server import utils
from integrations.slack import users as slack_users
from server.utils import get_user_email_from_request
from unittest.mock import MagicMock
from fastapi import HTTPException


def test_log_ops_message():
    client = MagicMock()
    msg = "foo bar baz"
    utils.log_ops_message(client, msg)
    client.chat_postMessage.assert_called_with(
        channel="C0388M21LKZ", text=msg, as_user=True
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


def test_get_user_id_from_request_found():
    # Mock the session data
    mock_request = MagicMock()
    mock_request.session = {"user": {"email": "test@example.com"}}

    user_email = get_user_email_from_request(mock_request)
    assert user_email == "test@example.com"


def test_get_user_id_from_request_not_found():
    # Mock the session data with no email
    mock_request = MagicMock()
    mock_request.session = {"user": {}}

    user_email = get_user_email_from_request(mock_request)
    assert user_email is None


def test_get_user_id_from_request_no_user():
    # Mock the session data with no user key
    mock_request = MagicMock()
    mock_request.session = {}

    with pytest.raises(HTTPException) as excinfo:
        get_user_email_from_request(mock_request)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Invalid request or missing session data"


def test_get_user_email_from_request_no_session():
    # Mock the request with no session data
    mock_request = MagicMock()
    mock_request.session = None

    with pytest.raises(HTTPException) as excinfo:
        get_user_email_from_request(mock_request)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Invalid request or missing session data"
