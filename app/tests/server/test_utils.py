from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from integrations.slack import users as slack_users
from jose import JWTError  # type: ignore
from server import utils
from server.utils import create_access_token, get_user_email_from_request

TEST_SECRET_KEY = "test_secret_key"
TEST_ALGORITHM = "test_algorithm"
TEST_ACCESS_TOKEN_EXPIRE_MINUTES = 30


@pytest.fixture(autouse=True)
def mock_settings():
    with patch("server.utils.SECRET_KEY", "test_secret_key"):
        with patch("server.utils.ALGORITHM", "test_algorithm"):
            with patch("server.utils.ACCESS_TOKEN_EXPIRE_MINUTES", 30):
                yield


@pytest.fixture(autouse=True)
def mock_datetime():
    """Mock datetime to control the current time during tests."""
    with patch("server.utils.datetime") as mocked_datetime:
        mocked_datetime.now.return_value = datetime(2023, 10, 1, 12, 0, 0)
        yield mocked_datetime


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


@patch("server.utils.jwt.encode")
def test_create_access_token_with_expires_delta(mock_jwt_encode):
    data = {"sub": "testuser"}
    expires = timedelta(minutes=10)
    mock_jwt_encode.return_value = "mocked_token"
    utc_now_value = datetime(2023, 10, 1, 12, 0, 0)

    token = create_access_token(data, expires)

    mock_jwt_encode.assert_called_once_with(
        {"sub": "testuser", "exp": utc_now_value + expires},
        "test_secret_key",
        algorithm="test_algorithm",
    )
    assert token == "mocked_token"


@patch("server.utils.jwt.encode")
def test_create_access_token_with_default_expiration(mock_jwt_encode):
    data = {"sub": "testuser"}
    mock_jwt_encode.return_value = "mocked_token"
    token = create_access_token(data)
    mock_jwt_encode.assert_called_once_with(
        {"sub": "testuser", "exp": datetime(2023, 10, 1, 12, 30, 0)},
        "test_secret_key",
        algorithm="test_algorithm",
    )
    assert token == "mocked_token"


@patch("server.utils.logger")
@patch("server.utils.jwt.encode")
def test_create_access_token_invalid_secret(mock_jwt_encode, mock_logger):
    data = {"sub": "testuser"}
    mock_jwt_encode.side_effect = JWTError("Some error")
    with pytest.raises(HTTPException) as excinfo:
        create_access_token(data)

    mock_jwt_encode.assert_called_once_with(
        {"sub": "testuser", "exp": datetime(2023, 10, 1, 12, 30, 0)},
        "test_secret_key",
        algorithm="test_algorithm",
    )

    mock_logger.error.assert_called_once_with("jwt_encoding_failed", error="Some error")
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Failed to encode JWT"


def test_create_access_token_negative_expiration():
    data = {"sub": "testuser"}
    expires = timedelta(minutes=-10)
    with pytest.raises(ValueError) as excinfo:
        create_access_token(data, expires)
    assert str(excinfo.value) == "expires_delta cannot be negative"


def test_create_access_token_large_expiration():
    data = {"sub": "testuser"}
    expires = timedelta(days=365)
    with pytest.raises(ValueError) as excinfo:
        create_access_token(data, expires)
    assert str(excinfo.value) == "expires_delta exceeds maximum allowed duration"


@pytest.fixture
def mock_request():
    request = AsyncMock(Request)
    request.session = {}
    request.cookies = {}
    return request


@pytest.fixture
def mock_token():
    token = MagicMock(spec=HTTPAuthorizationCredentials)
    token.credentials = "valid_token"
    return token


@pytest.mark.asyncio
async def test_get_current_user_no_token_or_cookie(mock_request):
    with pytest.raises(HTTPException) as exc_info:
        await utils.get_current_user(mock_request, None)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"


@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_with_valid_bearer_token(
    mock_jwt_decode, mock_request, mock_token
):
    mock_jwt_decode.return_value = {"sub": "testuser@example.com"}

    user = await utils.get_current_user(mock_request, mock_token)

    mock_jwt_decode.assert_called_once_with(
        "valid_token", TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM]
    )
    assert user == "testuser@example.com"


@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_with_valid_cookie(mock_jwt_decode, mock_request):
    mock_request.cookies = {"access_token": "cookie_token"}
    mock_jwt_decode.return_value = {"sub": "testuser@example.com"}

    user = await utils.get_current_user(mock_request, None)

    mock_jwt_decode.assert_called_once_with(
        "cookie_token", TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM]
    )
    assert user == "testuser@example.com"


@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_bearer_token_priority(
    mock_jwt_decode, mock_request, mock_token
):
    # Setup both bearer token and cookie
    mock_request.cookies = {"access_token": "cookie_token"}
    mock_jwt_decode.return_value = {"sub": "testuser@example.com"}

    user = await utils.get_current_user(mock_request, mock_token)

    # Verify bearer token was used, not cookie
    mock_jwt_decode.assert_called_once_with(
        "valid_token", TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM]
    )
    assert user == "testuser@example.com"


@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_invalid_bearer_token(
    mock_jwt_decode, mock_request, mock_token
):
    mock_jwt_decode.side_effect = JWTError("Invalid token")

    with pytest.raises(HTTPException) as exc_info:
        await utils.get_current_user(mock_request, mock_token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_invalid_cookie_token(mock_jwt_decode, mock_request):
    mock_request.cookies = {"access_token": "invalid_cookie_token"}
    mock_jwt_decode.side_effect = JWTError("Invalid token")

    with pytest.raises(HTTPException) as exc_info:
        await utils.get_current_user(mock_request, None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_token_missing_sub(
    mock_jwt_decode, mock_request, mock_token
):
    mock_jwt_decode.return_value = {"some_field": "value_without_sub"}

    with pytest.raises(HTTPException) as exc_info:
        await utils.get_current_user(mock_request, mock_token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"
