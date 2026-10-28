"""Tests for the GC Notify client: the JWT, the authorization header and the key revocation.

The client reads the Notify slice at use through ``get_notify_settings``, which each test
patches with a real ``NotifySettings`` (``model_construct``, so no configuration files are
needed): a renamed field then raises instead of returning a mock child. Outbound calls are
stubbed at ``post_event`` or ``requests.post``; no test reaches the network.
"""

import json
from unittest.mock import MagicMock, patch

import jwt
import pytest
from freezegun import freeze_time
from pydantic import SecretStr
from structlog.testing import capture_logs

from integrations.notify import client as notify
from integrations.notify.settings import NotifySettings, NotifyTenant

API_URL = "https://notify.example.com"


def _settings(
    tenant: NotifyTenant | None = NotifyTenant(api_url=API_URL), user: str = "test-client-id", secret: str = "test-secret"
) -> NotifySettings:
    return NotifySettings.model_construct(
        tenant=tenant, sre_user_name=SecretStr(user), sre_client_secret=SecretStr(secret), timeout_seconds=42.0
    )


@pytest.fixture(autouse=True)
def notify_settings():
    """Serve a configured slice to the client unless a test patches another."""
    settings = _settings()
    with patch("integrations.notify.client.get_notify_settings", return_value=settings):
        yield settings


def decode_token(token, secret):
    return jwt.decode(token, key=secret, options={"verify_signature": True}, algorithms=["HS256"])


# Test that an exception is raised if the secret is missing
@patch("integrations.notify.client.logger")
def test_create_jwt_token_secret_missing(mock_logger):
    bound_logger_mock = mock_logger.bind.return_value
    with pytest.raises(ValueError) as err:
        notify.create_jwt_token(None, "client_id")
    assert str(err.value) == "Missing secret key"
    bound_logger_mock.error.assert_called_once_with("jwt_token_creation_failed", error="Missing secret key")


# Test that an exception is raised if the client_id is missing
@patch("integrations.notify.client.logger")
def test_create_jwt_token_client_id_missing(mock_logger):
    bound_logger_mock = mock_logger.bind.return_value
    with pytest.raises(ValueError) as err:
        notify.create_jwt_token("secret", None)
    assert str(err.value) == "Missing client id"
    bound_logger_mock.error.assert_called_once_with("jwt_token_creation_failed", error="Missing client id")


# Test that the token is created correctly and the type and alg headers are set correctly
def test_create_jwt_token_contains_correct_headers():
    token = notify.create_jwt_token("secret", "client_id")
    headers = jwt.get_unverified_header(token)
    assert headers["typ"] == "JWT"
    assert headers["alg"] == "HS256"


# Test that the claims headers are set correctly
def test_create_jwt_token_contains_correct_claims_headers():
    token = notify.create_jwt_token("secret", "client_id")
    decoded_token = decode_token(token, "secret")
    assert decoded_token["iss"] == "client_id"
    assert "iat" in decoded_token
    assert "req" not in decoded_token
    assert "pay" not in decoded_token


@patch("integrations.notify.client.jwt.encode")
def test_create_jwt_token_with_bytes_return(mock_jwt_encode):
    mock_jwt_encode.return_value = b"encoded_token_as_bytes"

    token = notify.create_jwt_token("secret", "client_id")

    assert isinstance(token, str)
    assert token == "encoded_token_as_bytes"

    mock_jwt_encode.assert_called_once()
    call_args = mock_jwt_encode.call_args[1]
    assert call_args["key"] == "secret"
    assert call_args["headers"] == {"typ": "JWT", "alg": "HS256"}
    assert call_args["payload"]["iss"] == "client_id"


# Test that the correct iat time in epoch seconds is set correctly
@freeze_time("2020-01-01 00:00:00")
def test_token_contains_correct_iat():
    token = notify.create_jwt_token("secret", "client_id")
    decoded_token = decode_token(token, "secret")
    assert decoded_token["iat"] == 1577836800


@patch("integrations.notify.client.logger")
@patch("integrations.notify.client.create_jwt_token")
def test_authorization_header_missing_client_id(mock_jwt_token, mock_logger):
    with patch("integrations.notify.client.get_notify_settings", return_value=_settings(user="")):
        with pytest.raises(ValueError) as err:
            notify.create_authorization_header()
    assert str(err.value) == "NOTIFY__SRE_USER_NAME is missing"
    mock_logger.error.assert_called_once_with("authorization_header_creation_failed", error="NOTIFY__SRE_USER_NAME is missing")
    mock_jwt_token.assert_not_called()


@patch("integrations.notify.client.logger")
@patch("integrations.notify.client.create_jwt_token")
def test_authorization_header_missing_secret(mock_jwt_token, mock_logger):
    with patch("integrations.notify.client.get_notify_settings", return_value=_settings(secret="")):
        with pytest.raises(ValueError) as err:
            notify.create_authorization_header()
    assert str(err.value) == "NOTIFY__SRE_CLIENT_SECRET is missing"
    mock_logger.error.assert_called_once_with(
        "authorization_header_creation_failed", error="NOTIFY__SRE_CLIENT_SECRET is missing"
    )
    mock_jwt_token.assert_not_called()


@patch("integrations.notify.client.create_jwt_token")
def test_successful_creation_of_header(mock_jwt_token):
    """The JWT is signed with the slice's credentials."""
    mock_jwt_token.return_value = "mocked_jwt_token"
    header_key, header_value = notify.create_authorization_header()

    assert header_key == "Authorization"
    assert header_value == "Bearer mocked_jwt_token"
    mock_jwt_token.assert_called_once_with(secret="test-secret", client_id="test-client-id")


@patch("integrations.notify.client.requests.post")
@patch("integrations.notify.client.create_authorization_header")
def test_post_event_uses_the_slice_timeout(mock_auth_header, mock_post):
    mock_auth_header.return_value = ("Auth-Header", "auth-value")
    test_url = "https://api.notify.example.com/endpoint"
    test_payload = {"key1": "value1", "key2": "value2"}

    response = notify.post_event(test_url, test_payload)

    assert response == mock_post.return_value
    mock_post.assert_called_once_with(
        test_url,
        data=json.dumps(test_payload),
        headers={"Auth-Header": "auth-value", "Content-Type": "application/json"},
        timeout=42.0,
    )


@patch("integrations.notify.client.requests.post")
def test_revoke_api_key_without_a_tenant_is_not_configured(mock_post):
    """No [notify.tenant]: the revoke returns error, logs it and makes no HTTP call, whatever ENVIRONMENT says."""
    with (
        patch("integrations.notify.client.get_notify_settings", return_value=_settings(tenant=None, user="", secret="")),
        capture_logs() as entries,
    ):
        result = notify.revoke_api_key("api-key-123", "api-type", "github.com/repo", "test")

    assert result == "error"
    assert [entry["event"] for entry in entries] == ["revoke_api_key_not_configured"]
    mock_post.assert_not_called()


def test_revoke_api_key_does_not_read_the_environment_name(monkeypatch):
    """With a tenant, the revoke is attempted under any ENVIRONMENT: the entry alone decides."""
    monkeypatch.setenv("ENVIRONMENT", "ci")
    response = MagicMock(status_code=201)
    with patch("integrations.notify.client.post_event", return_value=response) as mock_post_event:
        assert notify.revoke_api_key("api-key-123", "api-type", "github.com/repo", "test") == "revoked"

    mock_post_event.assert_called_once()
    assert not hasattr(notify, "host_info")


@patch("integrations.notify.client.post_event")
@patch("integrations.notify.client.logger")
def test_revoke_api_key_success(mock_logger, mock_post_event):
    mock_post_event.return_value = MagicMock(status_code=201)
    api_key = "test-api-key-123"

    result = notify.revoke_api_key(api_key, "test-type", "github.com/test/repo", "test-source")

    assert result == "revoked"
    mock_post_event.assert_called_once_with(
        f"{API_URL}/sre-tools/api-key-revoke",
        {"token": api_key, "type": "test-type", "url": "github.com/test/repo", "source": "test-source"},
    )
    mock_logger.bind.return_value.info.assert_called_once_with("revoke_api_key_success", api_key=api_key)


@patch("integrations.notify.client.post_event")
def test_revoke_api_key_tolerates_a_trailing_slash(mock_post_event):
    mock_post_event.return_value = MagicMock(status_code=201)
    settings = _settings(tenant=NotifyTenant(api_url=f"{API_URL}/"))

    with patch("integrations.notify.client.get_notify_settings", return_value=settings):
        notify.revoke_api_key("k", "t", "r", "s")

    assert mock_post_event.call_args.args[0] == f"{API_URL}/sre-tools/api-key-revoke"


@patch("integrations.notify.client.post_event")
@patch("integrations.notify.client.logger")
def test_revoke_api_key_failure(mock_logger, mock_post_event):
    mock_post_event.return_value = MagicMock(status_code=400)
    api_key = "test-api-key-123"

    result = notify.revoke_api_key(api_key, "test-type", "github.com/test/repo", "test-source")

    assert result == "error"
    assert mock_post_event.call_args.args[0] == f"{API_URL}/sre-tools/api-key-revoke"
    mock_logger.bind.return_value.error.assert_called_once_with("revoke_api_key_error", api_key=api_key, response_code=400)


@patch("integrations.notify.client.post_event")
@patch("integrations.notify.client.logger")
def test_revoke_api_key_not_found(mock_logger, mock_post_event):
    mock_post_event.return_value = MagicMock(status_code=200)
    api_key = "test-api-key-123"

    result = notify.revoke_api_key(api_key, "test-type", "github.com/test/repo", "test-source")

    assert result == "not_found"
    mock_logger.bind.return_value.warning.assert_called_once_with("revoke_api_key_not_found", api_key=api_key)
