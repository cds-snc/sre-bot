"""Tests for security identity value types."""

import importlib

import pytest
from pydantic import BaseModel

from infrastructure.security.models import AuthPrincipalSource, User


@pytest.mark.unit
def test_user_model_importable_from_security_models() -> None:
    """User is exposed from infrastructure.security.models."""
    assert User is not None


@pytest.mark.unit
def test_auth_principal_source_importable_from_security_models() -> None:
    """AuthPrincipalSource is exposed from infrastructure.security.models."""
    assert AuthPrincipalSource is not None


@pytest.mark.unit
def test_user_has_required_fields() -> None:
    """User accepts the required auth principal fields."""
    user = User(
        user_id="user@example.com",
        email="user@example.com",
        display_name="User Example",
        source=AuthPrincipalSource.API_JWT,
        platform_id="user@example.com",
    )

    assert user.user_id == "user@example.com"
    assert user.email == "user@example.com"
    assert user.display_name == "User Example"
    assert user.source == AuthPrincipalSource.API_JWT
    assert user.platform_id == "user@example.com"


@pytest.mark.unit
def test_auth_principal_source_has_all_values() -> None:
    """AuthPrincipalSource preserves all supported sources."""
    assert AuthPrincipalSource.API_JWT.value == "api_jwt"
    assert AuthPrincipalSource.SLACK.value == "slack"
    assert AuthPrincipalSource.WEBHOOK.value == "webhook"
    assert AuthPrincipalSource.SYSTEM.value == "system"


@pytest.mark.unit
def test_user_is_pydantic_base_model() -> None:
    """User remains a transport-layer Pydantic model."""
    user = User(
        user_id="user@example.com",
        email="user@example.com",
        display_name="User Example",
        source=AuthPrincipalSource.API_JWT,
        platform_id="user@example.com",
    )

    assert isinstance(user, BaseModel)


@pytest.mark.unit
def test_slack_user_not_exported_from_security_models() -> None:
    """SlackUser is removed as part of identity package dissolution."""
    with pytest.raises(AttributeError):
        importlib.import_module("infrastructure.security.models").SlackUser
