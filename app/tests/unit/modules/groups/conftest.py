"""Unit test fixtures for groups module."""

import types
from typing import Dict, Any
from unittest.mock import MagicMock
import pytest

# Import provider registry so we can reset it between tests to avoid
# cross-test state pollution from provider activation tests.
from modules.groups.providers import PROVIDER_REGISTRY as _PROV_REG


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
            providers={
                "google": {"enabled": True, "primary": True, "prefix": "g"},
                "aws": {"enabled": True, "primary": False, "prefix": "aws"},
            },
        )
    )


@pytest.fixture
def mock_primary_provider():
    """Mock primary provider with is_manager method.

    Returns a MagicMock configured as PrimaryGroupProvider with:
    - is_manager() method
    - prefix, primary attributes

    Usage:
        provider = mock_primary_provider
        provider.is_manager.return_value = True
    """
    provider = MagicMock()
    provider.prefix = "g"
    provider.primary = True
    provider.is_manager = MagicMock(return_value=True)
    return provider


@pytest.fixture
def mock_secondary_provider():
    """Mock secondary provider without is_manager method.

    Returns a MagicMock configured as secondary provider with:
    - prefix, primary attributes
    - NO is_manager() method (not part of contract)

    Usage:
        provider = mock_secondary_provider
        provider.add_member = MagicMock(return_value=...)
    """
    provider = MagicMock()
    provider.prefix = "aws"
    provider.primary = False
    # Explicitly remove is_manager to match secondary provider contract
    provider.is_manager = None
    return provider


@pytest.fixture
def mock_providers_registry(mock_primary_provider, mock_secondary_provider):
    """Mock provider registry with google primary and aws secondary.

    Returns dict mapping provider names to mock instances.

    Usage:
        with patch("modules.groups.providers.get_active_providers", return_value=mock_providers_registry):
            ...
    """
    return {
        "google": mock_primary_provider,
        "aws": mock_secondary_provider,
    }


# Ensure provider registry is reset to a stable baseline for each unit test
# to avoid cross-test pollution when tests directly mutate the global
# `PROVIDER_REGISTRY` in `modules.groups.providers`.
_PROV_REG_BASELINE = dict(_PROV_REG)


@pytest.fixture(autouse=True)
def _reset_provider_registry():
    """Reset `modules.groups.providers.PROVIDER_REGISTRY` to a known baseline
    before and after each test to ensure tests don't leak state between them.

    Tests that intentionally manipulate the registry (provider activation
    tests) may still run correctly because they explicitly set/clear the
    registry; this fixture simply guarantees isolation between tests.
    """
    # restore baseline before test
    _PROV_REG.clear()
    _PROV_REG.update(_PROV_REG_BASELINE)
    try:
        yield
    finally:
        # restore baseline after test
        _PROV_REG.clear()
        _PROV_REG.update(_PROV_REG_BASELINE)


@pytest.fixture(autouse=True)
def _patch_mappings_helpers(monkeypatch, mock_providers_registry):
    """Patch mapping module helpers to use the test provider registry.

    Many unit tests call mapping helpers without passing an explicit
    `provider_registry`. Patch `modules.groups.mappings.get_active_providers`
    and `get_primary_provider_name` to return the controlled test registry so
    mapping logic is deterministic and isolated from global activation state.
    """
    # Accept arbitrary args/kwargs to match real function signature which may
    # accept a provider_filter parameter in some call sites.
    monkeypatch.setattr(
        "modules.groups.mappings.get_active_providers",
        lambda *a, **kw: mock_providers_registry,
        raising=False,
    )
    monkeypatch.setattr(
        "modules.groups.mappings.get_primary_provider_name",
        lambda: "google",
        raising=False,
    )

    # Also patch the service-facing provider helpers so that code which calls
    # `modules.groups.service._providers.get_active_providers` or
    # `modules.groups.service._providers.get_primary_provider_name` sees the
    # same deterministic test registry and primary provider name.
    monkeypatch.setattr(
        "modules.groups.service._providers.get_active_providers",
        lambda *a, **kw: mock_providers_registry,
        raising=False,
    )
    monkeypatch.setattr(
        "modules.groups.service._providers.get_primary_provider_name",
        lambda: "google",
        raising=False,
    )
    yield


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
