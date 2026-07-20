"""Behavior tests for dev-bypass guard semantics in get_current_user."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, SecurityScopes

from infrastructure.configuration.app import AppSettings
from infrastructure.security.current_user import get_current_user


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _jwt_failure() -> HTTPException:
    return HTTPException(status_code=401, detail="jwt_validation_failed")


@pytest.mark.unit
@patch("infrastructure.security.current_user.validate_jwt_token")
@patch("infrastructure.security.current_user.get_app_settings")
@patch("infrastructure.security.current_user.get_server_settings")
def test_bypass_denied_when_environment_is_production(
    mock_get_server_settings,
    mock_get_app_settings,
    mock_validate_jwt_token,
) -> None:
    """Bypass must be denied in production even when token matches."""
    mock_get_server_settings.return_value = MagicMock(DEV_BYPASS_TOKEN="dev-token")
    mock_get_app_settings.return_value = AppSettings(
        ENVIRONMENT="production", DEV_BYPASS_ENABLED=True
    )
    mock_validate_jwt_token.side_effect = _jwt_failure()

    with pytest.raises(HTTPException, match="jwt_validation_failed"):
        get_current_user(
            security_scopes=SecurityScopes(scopes=["sre-bot:access-sync"]),
            credentials=_credentials("dev-token"),
            jwks_manager=MagicMock(),
        )


@pytest.mark.unit
@patch("infrastructure.security.current_user.validate_jwt_token")
@patch("infrastructure.security.current_user.get_app_settings")
@patch("infrastructure.security.current_user.get_server_settings")
def test_bypass_denied_when_bypass_disabled(
    mock_get_server_settings,
    mock_get_app_settings,
    mock_validate_jwt_token,
) -> None:
    """Bypass must be denied when DEV_BYPASS_ENABLED is false."""
    mock_get_server_settings.return_value = MagicMock(DEV_BYPASS_TOKEN="dev-token")
    mock_get_app_settings.return_value = AppSettings(
        ENVIRONMENT="local", DEV_BYPASS_ENABLED=False
    )
    mock_validate_jwt_token.side_effect = _jwt_failure()

    with pytest.raises(HTTPException, match="jwt_validation_failed"):
        get_current_user(
            security_scopes=SecurityScopes(scopes=["sre-bot:access-sync"]),
            credentials=_credentials("dev-token"),
            jwks_manager=MagicMock(),
        )


@pytest.mark.unit
@patch("infrastructure.security.current_user.validate_jwt_token")
@patch("infrastructure.security.current_user.get_app_settings")
@patch("infrastructure.security.current_user.get_server_settings")
def test_bypass_denied_when_token_mismatch(
    mock_get_server_settings,
    mock_get_app_settings,
    mock_validate_jwt_token,
) -> None:
    """Bypass must be denied when the presented token does not match."""
    mock_get_server_settings.return_value = MagicMock(DEV_BYPASS_TOKEN="dev-token")
    mock_get_app_settings.return_value = AppSettings(
        ENVIRONMENT="local", DEV_BYPASS_ENABLED=True
    )
    mock_validate_jwt_token.side_effect = _jwt_failure()

    with pytest.raises(HTTPException, match="jwt_validation_failed"):
        get_current_user(
            security_scopes=SecurityScopes(scopes=["sre-bot:access-sync"]),
            credentials=_credentials("wrong-token"),
            jwks_manager=MagicMock(),
        )


@pytest.mark.unit
@patch("infrastructure.security.current_user.logger")
@patch("infrastructure.security.current_user.validate_jwt_token")
@patch("infrastructure.security.current_user.get_app_settings")
@patch("infrastructure.security.current_user.get_server_settings")
def test_bypass_allowed_and_logged(
    mock_get_server_settings,
    mock_get_app_settings,
    mock_validate_jwt_token,
    mock_logger,
) -> None:
    """Bypass should return synthetic user and log when both guards pass."""
    mock_get_server_settings.return_value = MagicMock(DEV_BYPASS_TOKEN="dev-token")
    mock_get_app_settings.return_value = AppSettings(
        ENVIRONMENT="local", DEV_BYPASS_ENABLED=True
    )

    user = get_current_user(
        security_scopes=SecurityScopes(scopes=["sre-bot:access-sync"]),
        credentials=_credentials("dev-token"),
        jwks_manager=MagicMock(),
    )

    assert user.user_id == "dev@local"
    assert user.permissions == ["sre-bot:access-sync"]
    mock_validate_jwt_token.assert_not_called()
    mock_logger.bind.assert_called_once_with(bypass="dev_token")
    mock_logger.bind.return_value.warning.assert_called_once_with(
        "dev_bypass_token_used"
    )