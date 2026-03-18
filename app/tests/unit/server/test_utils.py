"""Unit tests for server.utils module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError  # type: ignore

from server import utils
from server.utils import create_access_token, get_user_email_from_request


TEST_SECRET_KEY = "test_secret_key"
TEST_ALGORITHM = "HS256"
TEST_ACCESS_TOKEN_EXPIRE_MINUTES = 30


@pytest.fixture(autouse=True)
def mock_settings_for_utils(monkeypatch):
    """Mock settings for server.utils module."""
    monkeypatch.setattr("server.utils.SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setattr("server.utils.ALGORITHM", TEST_ALGORITHM)
    monkeypatch.setattr(
        "server.utils.ACCESS_TOKEN_EXPIRE_MINUTES", TEST_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    monkeypatch.setattr("server.utils.ACCESS_TOKEN_MAX_AGE_MINUTES", 60)


@pytest.fixture(autouse=True)
def mock_datetime_for_utils(monkeypatch):
    """Mock datetime to control the current time during tests."""
    base_time = datetime(2023, 10, 1, 12, 0, 0, tzinfo=timezone.utc)

    class MockDatetime:
        @staticmethod
        def now(tz=None):
            if tz:
                return base_time
            return base_time.replace(tzinfo=None)

        def __add__(self, other):
            return base_time + other

        def __sub__(self, other):
            return base_time - other

    monkeypatch.setattr(
        "server.utils.datetime",
        MagicMock(
            now=MagicMock(return_value=base_time),
            side_effect=lambda *args, **kwargs: (
                base_time if args == () else datetime(*args, **kwargs)
            ),
        ),
    )


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request object."""
    request = AsyncMock(spec=Request)
    request.session = {}
    request.cookies = {}
    return request


@pytest.fixture
def mock_token():
    """Create a mock HTTPAuthorizationCredentials object."""
    token = MagicMock(spec=HTTPAuthorizationCredentials)
    token.credentials = "valid_token"
    return token


# Tests for create_access_token


@pytest.mark.unit
@patch("server.utils.jwt.encode")
def test_create_access_token_should_encode_with_expiration(mock_jwt_encode):
    """Test that create_access_token encodes data with expiration time."""
    # Arrange
    data = {"sub": "testuser"}
    expires = timedelta(minutes=10)
    mock_jwt_encode.return_value = "mocked_token"

    # Act
    token = create_access_token(data, expires)

    # Assert
    assert token == "mocked_token"
    mock_jwt_encode.assert_called_once()
    call_args = mock_jwt_encode.call_args
    assert call_args[0][1] == TEST_SECRET_KEY
    assert call_args[1]["algorithm"] == TEST_ALGORITHM


@pytest.mark.unit
@patch("server.utils.jwt.encode")
def test_create_access_token_should_use_default_expiration_when_not_provided(
    mock_jwt_encode,
):
    """Test that create_access_token uses default expiration when not provided."""
    # Arrange
    data = {"sub": "testuser"}
    mock_jwt_encode.return_value = "mocked_token"

    # Act
    token = create_access_token(data)

    # Assert
    assert token == "mocked_token"
    mock_jwt_encode.assert_called_once()


@pytest.mark.unit
def test_create_access_token_should_reject_negative_expiration():
    """Test that create_access_token rejects negative expiration time."""
    # Arrange
    data = {"sub": "testuser"}
    expires = timedelta(minutes=-10)

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        create_access_token(data, expires)
    assert "cannot be negative" in str(exc_info.value)


@pytest.mark.unit
def test_create_access_token_should_reject_excessive_expiration():
    """Test that create_access_token rejects expiration exceeding maximum."""
    # Arrange
    data = {"sub": "testuser"}
    expires = timedelta(days=365)

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        create_access_token(data, expires)
    assert "exceeds maximum" in str(exc_info.value)


@pytest.mark.unit
@patch("server.utils.jwt.encode")
@patch("server.utils.logger")
def test_create_access_token_should_handle_jwt_encoding_error(
    mock_logger, mock_jwt_encode
):
    """Test that create_access_token handles JWT encoding errors."""
    # Arrange
    data = {"sub": "testuser"}
    mock_jwt_encode.side_effect = JWTError("Encoding failed")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        create_access_token(data)

    assert exc_info.value.status_code == 400
    assert "Failed to encode JWT" in exc_info.value.detail
    mock_logger.error.assert_called()


# Tests for get_user_email_from_request


@pytest.mark.unit
def test_get_user_email_from_request_should_return_email_when_found():
    """Test that get_user_email_from_request returns email when present."""
    # Arrange
    mock_request = MagicMock()
    mock_request.session = {"user": {"email": "test@example.com"}}
    mock_request.__bool__ = lambda self: True

    # Act
    user_email = get_user_email_from_request(mock_request)

    # Assert
    assert user_email == "test@example.com"


@pytest.mark.unit
def test_get_user_email_from_request_should_return_none_when_email_missing():
    """Test that get_user_email_from_request returns None when email is missing."""
    # Arrange
    mock_request = MagicMock()
    mock_request.session = {"user": {}}
    mock_request.__bool__ = lambda self: True

    # Act
    user_email = get_user_email_from_request(mock_request)

    # Assert
    assert user_email is None


@pytest.mark.unit
def test_get_user_email_from_request_should_raise_when_user_key_missing():
    """Test that get_user_email_from_request raises HTTPException when user key missing."""
    # Arrange
    mock_request = MagicMock(spec=Request)
    mock_request.session = {}

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        get_user_email_from_request(mock_request)
    assert exc_info.value.status_code == 400
    assert "session data" in exc_info.value.detail


@pytest.mark.unit
def test_get_user_email_from_request_should_raise_when_session_none():
    """Test that get_user_email_from_request raises HTTPException when session is None."""
    # Arrange
    mock_request = MagicMock(spec=Request)
    mock_request.session = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        get_user_email_from_request(mock_request)
    assert exc_info.value.status_code == 400
    assert "session data" in exc_info.value.detail


@pytest.mark.unit
def test_get_user_email_from_request_should_raise_when_request_none():
    """Test that get_user_email_from_request raises HTTPException when request is None."""
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        get_user_email_from_request(None)
    assert exc_info.value.status_code == 400


# Tests for get_current_user


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_should_raise_when_token_missing(mock_request):
    """Test that get_current_user raises when both token and cookie are missing."""
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await utils.get_current_user(mock_request, None)
    assert exc_info.value.status_code == 401
    assert "Not authenticated" in exc_info.value.detail


@pytest.mark.unit
@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_should_extract_from_bearer_token(
    mock_jwt_decode, mock_request, mock_token
):
    """Test that get_current_user extracts user from bearer token."""
    # Arrange
    mock_jwt_decode.return_value = {"sub": "testuser@example.com"}

    # Act
    user = await utils.get_current_user(mock_request, mock_token)

    # Assert
    assert user == "testuser@example.com"
    mock_jwt_decode.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_should_extract_from_cookie_token(
    mock_jwt_decode, mock_request
):
    """Test that get_current_user extracts user from cookie when bearer token absent."""
    # Arrange
    mock_request.cookies = {"access_token": "cookie_token"}
    mock_jwt_decode.return_value = {"sub": "testuser@example.com"}

    # Act
    user = await utils.get_current_user(mock_request, None)

    # Assert
    assert user == "testuser@example.com"
    mock_jwt_decode.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_should_prefer_bearer_over_cookie(
    mock_jwt_decode, mock_request, mock_token
):
    """Test that get_current_user prefers bearer token over cookie."""
    # Arrange
    mock_request.cookies = {"access_token": "cookie_token"}
    mock_jwt_decode.return_value = {"sub": "testuser@example.com"}

    # Act
    user = await utils.get_current_user(mock_request, mock_token)

    # Assert
    assert user == "testuser@example.com"
    # Should be called with bearer token, not cookie
    call_args = mock_jwt_decode.call_args[0]
    assert call_args[0] == "valid_token"


@pytest.mark.unit
@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
@patch("server.utils.logger")
async def test_get_current_user_should_raise_on_invalid_token(
    mock_logger, mock_jwt_decode, mock_request, mock_token
):
    """Test that get_current_user raises on invalid token."""
    # Arrange
    mock_jwt_decode.side_effect = JWTError("Invalid token")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await utils.get_current_user(mock_request, mock_token)
    assert exc_info.value.status_code == 401
    assert "Invalid token" in exc_info.value.detail


@pytest.mark.unit
@pytest.mark.asyncio
@patch("server.utils.jwt.decode")
async def test_get_current_user_should_raise_when_sub_missing(
    mock_jwt_decode, mock_request, mock_token
):
    """Test that get_current_user raises when 'sub' claim is missing."""
    # Arrange
    mock_jwt_decode.return_value = {"some_field": "value"}

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await utils.get_current_user(mock_request, mock_token)
    assert exc_info.value.status_code == 401
    assert "Invalid token" in exc_info.value.detail
