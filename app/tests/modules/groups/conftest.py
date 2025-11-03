"""Shared fixtures for groups module tests."""

import types
from typing import Dict, Any
import pytest
from unittest.mock import MagicMock
from modules.groups.models import NormalizedMember, NormalizedGroup
from modules.groups.providers.base import OperationResult, OperationStatus


@pytest.fixture
def mock_circuit_breaker_settings():
    """Mock settings object with circuit breaker configuration.

    Returns a SimpleNamespace with groups attribute containing all required
    circuit breaker settings. Use this to patch core.config.settings.

    Usage:
        with patch("core.config.settings", mock_circuit_breaker_settings):
            provider = GoogleWorkspaceProvider()
    """
    return types.SimpleNamespace(
        groups=types.SimpleNamespace(
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_timeout_seconds=60,
            circuit_breaker_half_open_max_calls=3,
            # Also include providers dict for legacy compatibility
            providers={},
        )
    )


@pytest.fixture
def mock_circuit_breaker_settings_disabled():
    """Mock settings with circuit breaker disabled."""
    return types.SimpleNamespace(
        groups=types.SimpleNamespace(
            circuit_breaker_enabled=False,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_timeout_seconds=60,
            circuit_breaker_half_open_max_calls=3,
            providers={},
        )
    )


@pytest.fixture
def normalized_member_factory():
    """Factory for creating NormalizedMember test instances.

    Usage:
        member = normalized_member_factory(
            email="test@example.com",
            id="user-123",
            role="member"
        )
    """

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
    """Factory for creating NormalizedGroup test instances.

    Usage:
        group = normalized_group_factory(
            id="group-123",
            name="Test Group",
            provider="google"
        )
    """

    def _factory(
        id: str = "group-1",
        name: str = "Test Group",
        description: str = "Test description",
        provider: str = "test",
        email: str = None,
        members: list = None,
        raw: Dict[str, Any] = None,
    ) -> NormalizedGroup:
        return NormalizedGroup(
            id=id,
            name=name,
            description=description,
            provider=provider,
            email=email,
            members=members or [],
            raw=raw,
        )

    return _factory


@pytest.fixture
def operation_result_factory():
    """Factory for creating OperationResult test instances.

    Usage:
        result = operation_result_factory(
            status=OperationStatus.SUCCESS,
            data={"added": True}
        )
    """

    def _factory(
        status: OperationStatus = OperationStatus.SUCCESS,
        message: str = "ok",
        data: Dict[str, Any] = None,
        error_code: str = None,
        retry_after: int = None,
    ) -> OperationResult:
        return OperationResult(
            status=status,
            message=message,
            data=data,
            error_code=error_code,
            retry_after=retry_after,
        )

    return _factory


@pytest.fixture
def mock_integration_client():
    """Mock integration client for provider tests.

    Returns a MagicMock configured for common integration patterns.

    Usage:
        provider = GoogleWorkspaceProvider()
        provider.integration = mock_integration_client
    """
    client = MagicMock()

    # Configure common methods
    client.list_groups.return_value = OperationResult.success(data=[])
    client.get_group.return_value = OperationResult.success(data={})
    client.add_group_member.return_value = OperationResult.success(data={})
    client.remove_group_member.return_value = OperationResult.success(data={})
    client.list_group_members.return_value = OperationResult.success(data=[])

    return client


@pytest.fixture
def patch_provider_init(monkeypatch, mock_circuit_breaker_settings):
    """Patch provider __init__ to skip circuit breaker initialization.

    This is useful for tests that want to instantiate providers without
    dealing with circuit breaker setup.

    Usage:
        def test_something(patch_provider_init):
            patch_provider_init("modules.groups.providers.google_workspace")
            provider = GoogleWorkspaceProvider()
            # provider._circuit_breaker will be None
    """

    def _patcher(module_path: str):
        """Patch the settings import in the specified provider module."""
        monkeypatch.setattr(
            f"{module_path}.base.settings", mock_circuit_breaker_settings, raising=False
        )

    return _patcher
