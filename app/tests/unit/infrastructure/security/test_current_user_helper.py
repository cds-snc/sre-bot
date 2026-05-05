"""Tests for JWT principal construction in current_user."""

import inspect

import pytest

from infrastructure.security.current_user import (
    _build_user_from_jwt_payload,
    get_current_user,
)
from infrastructure.security.models import AuthPrincipalSource, User


@pytest.mark.unit
def test_build_user_from_jwt_payload_returns_user() -> None:
    """JWT payload helper returns a normalized user."""
    payload = {
        "sub": "user@example.com",
        "email": "user@example.com",
        "name": "Example User",
        "permissions": ["read"],
        "iss": "issuer",
    }

    user = _build_user_from_jwt_payload(payload)

    assert isinstance(user, User)


@pytest.mark.unit
def test_build_user_from_jwt_payload_sets_api_jwt_source() -> None:
    """JWT payload helper tags users with API_JWT source."""
    user = _build_user_from_jwt_payload({"sub": "user@example.com"})

    assert user.source == AuthPrincipalSource.API_JWT


@pytest.mark.unit
def test_build_user_from_jwt_payload_uses_sub_as_user_id() -> None:
    """JWT payload helper uses sub as the canonical user ID."""
    user = _build_user_from_jwt_payload({"sub": "user@example.com"})

    assert user.user_id == "user@example.com"
    assert user.platform_id == "user@example.com"


@pytest.mark.unit
def test_build_user_from_jwt_payload_handles_missing_email() -> None:
    """JWT payload helper falls back when email is absent."""
    user = _build_user_from_jwt_payload({"sub": "user@example.com"})

    assert user.email == "unknown"


@pytest.mark.unit
def test_build_user_from_jwt_payload_handles_missing_name() -> None:
    """JWT payload helper falls back to sub when name is absent."""
    user = _build_user_from_jwt_payload({"sub": "user@example.com"})

    assert user.display_name == "user@example.com"


@pytest.mark.unit
def test_get_current_user_has_no_identity_service_param() -> None:
    """JWT auth dependency no longer accepts identity_service injection."""
    signature = inspect.signature(get_current_user)

    assert "identity_service" not in signature.parameters
