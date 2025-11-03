"""Unit test fixtures for groups module."""

import types
from typing import Dict, Any
import pytest


@pytest.fixture
def mock_settings_groups():
    """Mock core.config.settings with groups configuration.

    Returns a SimpleNamespace mimicking settings structure.
    """
    return types.SimpleNamespace(
        groups=types.SimpleNamespace(
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_timeout=60,
            circuit_breaker_half_open_max_calls=2,
            idempotency_cache_ttl=3600,
            reconciliation_backoff_base=60,
            reconciliation_backoff_max=3600,
            reconciliation_max_retries=3,
            primary_provider="google",
            providers={},
        )
    )


@pytest.fixture
def normalized_member_factory():
    """Factory for creating NormalizedMember instances.

    Usage:
        member = normalized_member_factory(
            email="test@example.com",
            role="member"
        )
    """
    from modules.groups.models import NormalizedMember

    def _factory(
        email: str = "test@example.com",
        id: str = "user-1",
        role: str = "member",
        provider_member_id: str = "provider-1",
        first_name: str = None,
        family_name: str = None,
        raw: Dict[str, Any] = None,
    ) -> NormalizedMember:
        return NormalizedMember(
            email=email,
            id=id,
            role=role,
            provider_member_id=provider_member_id,
            first_name=first_name,
            family_name=family_name,
            raw=raw,
        )

    return _factory


@pytest.fixture
def normalized_group_factory():
    """Factory for creating NormalizedGroup instances.

    Usage:
        group = normalized_group_factory(
            id="group-123",
            name="Test Group"
        )
    """
    from modules.groups.models import NormalizedGroup

    def _factory(
        id: str = "group-1",
        name: str = "Test Group",
        description: str = "Test description",
        provider: str = "test",
        members: list = None,
        raw: Dict[str, Any] = None,
    ) -> NormalizedGroup:
        return NormalizedGroup(
            id=id,
            name=name,
            description=description,
            provider=provider,
            members=members or [],
            raw=raw,
        )

    return _factory
