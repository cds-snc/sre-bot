"""Unit test fixtures for groups module."""

import types
from typing import Dict, Any
from unittest.mock import MagicMock, patch
import pytest
from modules.groups.providers.base import GroupProvider, PrimaryGroupProvider
from modules.groups.providers.contracts import (
    ProviderCapabilities,
    HealthCheckResult,
)
from infrastructure.operations import OperationResult, OperationStatus


class MockPrimaryGroupProvider(PrimaryGroupProvider):
    """Mock primary group provider for testing.

    Implements all required abstract methods from GroupProvider and PrimaryGroupProvider.
    """

    @property
    def capabilities(self):
        """Return mock capabilities for primary provider."""
        return ProviderCapabilities(is_primary=True, provides_role_info=True)

    def _add_member_impl(self, group_key: str, member_email: str):
        """Mock add member implementation."""
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def _remove_member_impl(self, group_key: str, member_email: str):
        """Mock remove member implementation."""
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def _get_group_members_impl(self, group_key: str, **kwargs):
        """Mock get group members implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS, message="ok", data={"members": []}
        )

    def _list_groups_impl(self, **kwargs):
        """Mock list groups implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS, message="ok", data={"groups": []}
        )

    def _list_groups_with_members_impl(self, **kwargs):
        """Mock list groups with members implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS, message="ok", data={"groups": []}
        )

    def _health_check_impl(self):
        """Mock health check implementation."""
        return HealthCheckResult(healthy=True, status="healthy")

    def _validate_permissions_impl(self, user_key: str, group_key: str, action: str):
        """Mock validate permissions implementation."""
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def _is_manager_impl(self, user_key: str, group_key: str):
        """Mock is manager implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS, message="ok", data={"is_manager": False}
        )


class MockGroupProvider(GroupProvider):
    """Mock secondary group provider for testing.

    Implements all required abstract methods from GroupProvider.
    """

    @property
    def capabilities(self):
        """Return mock capabilities for secondary provider."""
        return ProviderCapabilities(is_primary=False)

    def _add_member_impl(self, group_key: str, member_email: str):
        """Mock add member implementation."""
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def _remove_member_impl(self, group_key: str, member_email: str):
        """Mock remove member implementation."""
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def _get_group_members_impl(self, group_key: str, **kwargs):
        """Mock get group members implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS, message="ok", data={"members": []}
        )

    def _list_groups_impl(self, **kwargs):
        """Mock list groups implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS, message="ok", data={"groups": []}
        )

    def _list_groups_with_members_impl(self, **kwargs):
        """Mock list groups with members implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS, message="ok", data={"groups": []}
        )

    def _health_check_impl(self):
        """Mock health check implementation."""
        return HealthCheckResult(healthy=True, status="healthy")


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


@pytest.fixture(autouse=True)
def _reset_provider_registries(monkeypatch):
    """Reset provider registries to clean state between tests.

    With the new dual-registry approach (_primary_discovered, _primary_active,
    _secondary_discovered, _secondary_active), reset to ensure tests don't
    leak state between them.

    Tests that intentionally manipulate registries (provider activation tests)
    explicitly control this; this fixture ensures isolation.
    """
    import modules.groups.providers as providers

    # Store baseline state
    baseline_primary_discovered = dict(providers._primary_discovered)
    baseline_primary_active = providers._primary_active
    baseline_secondary_discovered = dict(providers._secondary_discovered)
    baseline_secondary_active = dict(providers._secondary_active)
    baseline_primary_name = providers._PRIMARY_PROVIDER_NAME

    try:
        yield
    finally:
        # Restore baseline after test
        providers._primary_discovered.clear()
        providers._primary_discovered.update(baseline_primary_discovered)
        providers._primary_active = baseline_primary_active
        providers._secondary_discovered.clear()
        providers._secondary_discovered.update(baseline_secondary_discovered)
        providers._secondary_active.clear()
        providers._secondary_active.update(baseline_secondary_active)
        providers._PRIMARY_PROVIDER_NAME = baseline_primary_name


@pytest.fixture(autouse=True)
def _patch_providers_helpers(monkeypatch, mock_providers_registry):
    """Patch provider helpers to use the test provider registry.

    Unit tests call provider helpers without passing an explicit
    `provider_registry`. Patch the provider helpers to return the controlled
    test registry so provider logic is deterministic and isolated from global
    activation state.
    """
    # Patch the service-facing provider helpers so that code which calls
    # `modules.groups.core.service._providers.get_active_providers` or
    # `modules.groups.core.service._providers.get_primary_provider_name` sees the
    # same deterministic test registry and primary provider name.
    monkeypatch.setattr(
        "modules.groups.core.service._providers.get_active_providers",
        lambda *a, **kw: mock_providers_registry,
        raising=False,
    )
    monkeypatch.setattr(
        "modules.groups.core.service._providers.get_primary_provider_name",
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
    from modules.groups.domain.models import NormalizedMember

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
    from modules.groups.domain.models import NormalizedGroup

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


# ============================================================================
# PROVIDER CONFIGURATION FIXTURES
# ============================================================================


@pytest.fixture
def mock_provider_config():
    """Factory for creating provider configuration dictionaries.

    Returns a function that generates provider config dicts with
    sensible defaults for testing configuration-driven provider activation.

    Usage:
        config = mock_provider_config(
            provider_name="google",
            enabled=True,
            primary=True,
            prefix="g",
            capabilities={"supports_member_management": True}
        )
    """
    from typing import Any, Optional

    def _factory(
        provider_name: str,
        enabled: bool = True,
        primary: bool = False,
        prefix: Optional[str] = None,
        capabilities: Optional[dict] = None,
    ) -> dict:
        config: dict[str, Any] = {"enabled": enabled}

        if primary:
            config["primary"] = True

        if prefix:
            config["prefix"] = prefix

        if capabilities:
            config["capabilities"] = capabilities

        return config

    return _factory


@pytest.fixture
def single_provider_config(mock_provider_config):
    """Provider configuration with single enabled primary provider.

    Used for testing behavior when only one provider is available.
    """
    google_cfg = mock_provider_config(
        provider_name="google",
        enabled=True,
        primary=True,
        prefix="g",
    )
    return {"google": google_cfg}


@pytest.fixture
def multi_provider_config(mock_provider_config):
    """Provider configuration with multiple enabled providers.

    Google as primary, AWS as secondary. Used for testing
    multi-provider scenarios.
    """
    google_cfg = mock_provider_config(
        provider_name="google",
        enabled=True,
        primary=True,
        prefix="g",
    )
    aws_cfg = mock_provider_config(
        provider_name="aws",
        enabled=True,
        primary=False,
        prefix="a",
    )
    return {**google_cfg, **aws_cfg}


@pytest.fixture
def disabled_provider_config(mock_provider_config):
    """Provider configuration with providers disabled.

    Used for testing behavior when no providers are available.
    """
    google_cfg = mock_provider_config(
        provider_name="google",
        enabled=False,
    )
    aws_cfg = mock_provider_config(
        provider_name="aws",
        enabled=False,
    )
    return {**google_cfg, **aws_cfg}


# ============================================================================
# GROUPS COMMANDS FIXTURES (from commands/conftest.py)
# ============================================================================


@pytest.fixture
def mock_translator():
    """Mock translator that returns input key with variable substitution."""

    def _translate(key: str, locale: str = "en-US", **variables):
        # Simple mock: replace {variable} with variable value
        result = key
        for var_name, var_value in variables.items():
            result = result.replace(f"{{{var_name}}}", str(var_value))
        return result

    return _translate


@pytest.fixture
def mock_command_context(mock_translator):
    """Create mock CommandContext for groups commands."""
    from tests.factories.groups_commands import make_groups_list_context

    ctx = make_groups_list_context()
    ctx._translator = mock_translator  # pylint: disable=protected-access

    # Mock responder
    mock_responder = MagicMock()
    mock_responder.send_message = MagicMock()
    mock_responder.send_ephemeral = MagicMock()
    ctx._responder = mock_responder  # pylint: disable=protected-access

    return ctx


@pytest.fixture
def mock_groups_service():
    """Mock groups service module for commands."""
    with patch("modules.groups.commands.handlers.service") as mock:
        yield mock


@pytest.fixture
def mock_slack_users():
    """Mock Slack users integration for commands."""
    with patch("modules.groups.commands.handlers.slack_users") as mock:
        mock.get_user_email_from_handle.return_value = "resolved@example.com"
        yield mock


@pytest.fixture
def mock_groups_provider():
    """Mock groups provider for commands."""
    with patch("modules.groups.commands.handlers.get_active_providers") as mock:
        mock.return_value = {
            "google": MagicMock(),
            "aws": MagicMock(),
            "azure": MagicMock(),
        }
        yield mock
