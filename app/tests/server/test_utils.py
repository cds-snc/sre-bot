import pytest
from server import utils
from jose import jwt, JWTError
from integrations.slack import users as slack_users
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import Request, HTTPException
from datetime import timedelta, datetime
from server.utils import create_access_token, get_user_email_from_request, SECRET_KEY, ALGORITHM


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
def test_create_access_token_with_expires_delta():
    data = {"sub": "testuser"}
    expires = timedelta(minutes=10)
    token = create_access_token(data, expires)
    decoded_data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded_data["sub"] == "testuser"
    assert "exp" in decoded_data
    expected_exp = datetime.utcnow() + expires
    assert abs(decoded_data["exp"] - int(expected_exp.timestamp())) < 5


def test_create_access_token_with_default_expiration():
    data = {"sub": "testuser"}
    token = create_access_token(data)
    decoded_data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded_data["sub"] == "testuser"
    assert "exp" in decoded_data
    expected_exp = datetime.utcnow() + timedelta(minutes=30)
    assert abs(decoded_data["exp"] - int(expected_exp.timestamp())) < 5


def test_create_access_token_invalid_secret():
    data = {"sub": "testuser"}
    token = create_access_token(data)
    with pytest.raises(JWTError):
        jwt.decode(token, "wrong_secret_key", algorithms=[ALGORITHM])


# Helper function to decode token safely
def decode_token(token):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def test_create_access_token_no_expiration():
    data = {"sub": "testuser"}
    token = create_access_token(data, expires_delta=None)
    decoded_data = decode_token(token)
    assert decoded_data["sub"] == "testuser"
    assert "exp" in decoded_data


def test_create_access_token_data_integrity():
    data = {"sub": "testuser", "role": "admin"}
    token = create_access_token(data)
    decoded_data = decode_token(token)
    assert decoded_data["sub"] == "testuser"
    assert decoded_data["role"] == "admin"
    assert "exp" in decoded_data


def test_create_access_token_negative_expiration():
    data = {"sub": "testuser"}
    expires = timedelta(minutes=-10)
    token = create_access_token(data, expires)
    with pytest.raises(JWTError):
        decode_token(token)


def test_create_access_token_large_expiration():
    data = {"sub": "testuser"}
    expires = timedelta(days=365)
    token = create_access_token(data, expires)
    decoded_data = decode_token(token)
    assert decoded_data["sub"] == "testuser"
    assert "exp" in decoded_data
    expected_exp = datetime.utcnow() + expires
    assert abs(decoded_data["exp"] - int(expected_exp.timestamp())) < 5


@pytest.fixture
def mock_request():
    request = AsyncMock(Request)
    request.session = {}
    return request


@pytest.mark.asyncio
async def test_get_current_user_no_token_or_session_user(mock_request):
    with pytest.raises(HTTPException) as exc_info:
        await utils.get_current_user(mock_request)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_invalid_token(mock_jwt_decode, mock_request):
    mock_request.session = {"access_token": "invalid_token"}
    mock_jwt_decode.side_effect = JWTError()

    with pytest.raises(HTTPException) as exc_info:
        await utils.get_current_user(mock_request)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_valid_token_no_user(mock_jwt_decode, mock_request):
    mock_request.session = {"access_token": "valid_token"}
    mock_jwt_decode.return_value = {"sub": None}

    with pytest.raises(HTTPException) as exc_info:
        await utils.get_current_user(mock_request)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_valid_token(mock_jwt_decode, mock_request):
    mock_request.session = {"access_token": "valid_token"}
    mock_jwt_decode.return_value = {"sub": "testuser"}

    user = await utils.get_current_user(mock_request)
    assert user == "testuser"


@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_no_token_but_session_user(
    mock_jwt_decode, mock_request
):
    with patch("server.utils.jwt.decode") as mock_jwt_decode:
        mock_request.session = {"user": {"email": "testuser@example.com"}}
        mock_jwt_decode.return_value = {"sub": "testuser"}
        user = await utils.get_current_user(mock_request)
        assert user == "testuser"


@pytest.mark.asyncio
async def test_get_current_user_with_token_and_session_user(mock_request):
    with patch("server.utils.jwt.decode") as mock_jwt_decode:
        mock_request.session = {
            "access_token": "valid_token",
            "user": {"email": "testuser@example.com"},
        }
        mock_jwt_decode.return_value = {"sub": "testuser"}
        user = await utils.get_current_user(mock_request)
        assert user == "testuser"
