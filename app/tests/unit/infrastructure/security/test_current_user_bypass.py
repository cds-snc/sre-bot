"""Behavior tests for dev-bypass guard semantics in get_current_user.

get_security_settings and host_info are patched in the current_user module
with a real SecuritySettings built without the .env file and a real HostInfo,
so a misspelled field fails construction instead of being silently ignored. JWT validation is patched
to fail, so a denied bypass surfaces as that failure.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, SecurityScopes
from pydantic import SecretStr

from contracts.configuration import HostInfo
from infrastructure.security.current_user import get_current_user
from infrastructure.security.settings import SecuritySettings


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _jwt_failure() -> HTTPException:
    return HTTPException(status_code=401, detail="jwt_validation_failed")


def _security(enabled: bool) -> SecuritySettings:
    return SecuritySettings(_env_file=None, dev_bypass_enabled=enabled, dev_bypass_token=SecretStr("dev-token"))


def _app(environment: str) -> HostInfo:
    return HostInfo(environment=environment, git_sha="test-sha", public_base_url="http://127.0.0.1:8000")


@pytest.mark.unit
@patch("infrastructure.security.current_user.validate_jwt_token")
@patch("infrastructure.security.current_user.host_info")
@patch("infrastructure.security.current_user.get_security_settings")
def test_bypass_denied_when_environment_is_prod(
    mock_get_security_settings,
    mock_host_info,
    mock_validate_jwt_token,
) -> None:
    """Bypass must be denied in production even when token matches."""
    mock_get_security_settings.return_value = _security(enabled=True)
    mock_host_info.return_value = _app("production")
    mock_validate_jwt_token.side_effect = _jwt_failure()

    with pytest.raises(HTTPException, match="jwt_validation_failed"):
        get_current_user(
            security_scopes=SecurityScopes(scopes=["sre-bot:access-sync"]),
            credentials=_credentials("dev-token"),
            jwks_manager=MagicMock(),
        )


@pytest.mark.unit
@patch("infrastructure.security.current_user.validate_jwt_token")
@patch("infrastructure.security.current_user.host_info")
@patch("infrastructure.security.current_user.get_security_settings")
def test_bypass_denied_when_bypass_disabled(
    mock_get_security_settings,
    mock_host_info,
    mock_validate_jwt_token,
) -> None:
    """Bypass must be denied when dev_bypass_enabled is false."""
    mock_get_security_settings.return_value = _security(enabled=False)
    mock_host_info.return_value = _app("local")
    mock_validate_jwt_token.side_effect = _jwt_failure()

    with pytest.raises(HTTPException, match="jwt_validation_failed"):
        get_current_user(
            security_scopes=SecurityScopes(scopes=["sre-bot:access-sync"]),
            credentials=_credentials("dev-token"),
            jwks_manager=MagicMock(),
        )


@pytest.mark.unit
@patch("infrastructure.security.current_user.validate_jwt_token")
@patch("infrastructure.security.current_user.host_info")
@patch("infrastructure.security.current_user.get_security_settings")
def test_bypass_denied_when_token_mismatch(
    mock_get_security_settings,
    mock_host_info,
    mock_validate_jwt_token,
) -> None:
    """Bypass must be denied when the presented token does not match."""
    mock_get_security_settings.return_value = _security(enabled=True)
    mock_host_info.return_value = _app("local")
    mock_validate_jwt_token.side_effect = _jwt_failure()

    with pytest.raises(HTTPException, match="jwt_validation_failed"):
        get_current_user(
            security_scopes=SecurityScopes(scopes=["sre-bot:access-sync"]),
            credentials=_credentials("wrong-token"),
            jwks_manager=MagicMock(),
        )


@pytest.mark.unit
@patch("infrastructure.security.current_user.validate_jwt_token")
@patch("infrastructure.security.current_user.host_info")
@patch("infrastructure.security.current_user.get_security_settings")
def test_bypass_denied_when_token_unset(
    mock_get_security_settings,
    mock_host_info,
    mock_validate_jwt_token,
) -> None:
    """Bypass must be denied when no dev_bypass_token is configured, even with the flag on."""
    mock_get_security_settings.return_value = SecuritySettings(_env_file=None, dev_bypass_enabled=True)
    mock_host_info.return_value = _app("local")
    mock_validate_jwt_token.side_effect = _jwt_failure()

    with pytest.raises(HTTPException, match="jwt_validation_failed"):
        get_current_user(
            security_scopes=SecurityScopes(scopes=["sre-bot:access-sync"]),
            credentials=_credentials(""),
            jwks_manager=MagicMock(),
        )


@pytest.mark.unit
@patch("infrastructure.security.current_user.logger")
@patch("infrastructure.security.current_user.validate_jwt_token")
@patch("infrastructure.security.current_user.host_info")
@patch("infrastructure.security.current_user.get_security_settings")
def test_bypass_allowed_and_logged(
    mock_get_security_settings,
    mock_host_info,
    mock_validate_jwt_token,
    mock_logger,
) -> None:
    """Bypass should return synthetic user and log the environment, never the token, when both guards pass."""
    mock_get_security_settings.return_value = _security(enabled=True)
    mock_host_info.return_value = _app("local")

    user = get_current_user(
        security_scopes=SecurityScopes(scopes=["sre-bot:access-sync"]),
        credentials=_credentials("dev-token"),
        jwks_manager=MagicMock(),
    )

    assert user.user_id == "dev@local"
    assert user.permissions == ["sre-bot:access-sync"]
    mock_validate_jwt_token.assert_not_called()
    mock_logger.bind.assert_called_once_with(bypass="dev_token", environment="local")
    mock_logger.bind.return_value.warning.assert_called_once_with("dev_bypass_token_used")
    assert "dev-token" not in str(mock_logger.mock_calls)
