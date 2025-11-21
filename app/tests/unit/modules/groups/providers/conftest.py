"""Unit test fixtures for groups providers."""

# pylint: disable=unused-argument

import pytest
import types
from typing import Optional

from modules.groups.providers.contracts import (
    ProviderCapabilities,
    OperationResult,
    OperationStatus,
)
from modules.groups.providers.base import GroupProvider, PrimaryGroupProvider


@pytest.fixture
def mock_google_directory_client(monkeypatch):
    """Mock Google Directory client for unit tests.

    Returns a factory function for creating configured mock clients.
    """

    def _factory(groups_data=None, members_data=None):
        client = types.SimpleNamespace(
            groups=types.SimpleNamespace(
                list=lambda **kwargs: types.SimpleNamespace(
                    execute=lambda: {"groups": groups_data or []}
                ),
                get=lambda **kwargs: types.SimpleNamespace(
                    execute=lambda: groups_data[0] if groups_data else {}
                ),
            ),
            members=types.SimpleNamespace(
                list=lambda **kwargs: types.SimpleNamespace(
                    execute=lambda: {"members": members_data or []}
                ),
            ),
        )
        return client

    return _factory


@pytest.fixture
def mock_identity_store_client(monkeypatch):
    """Mock AWS Identity Store client for unit tests.

    Returns a factory function for creating configured mock clients.
    """

    def _factory(groups_data=None, members_data=None):
        client = types.SimpleNamespace(
            list_groups=lambda **kwargs: {"Groups": groups_data or []},
            get_group=lambda **kwargs: (groups_data[0] if groups_data else {}),
            list_group_memberships=lambda **kwargs: {
                "GroupMemberships": members_data or []
            },
        )
        return client

    return _factory


@pytest.fixture
def sample_google_group_data():
    """Sample Google Workspace group data for tests."""
    return {
        "id": "group-123",
        "email": "developers@company.com",
        "name": "Developers",
        "description": "Development team",
        "directMembersCount": "5",
    }


@pytest.fixture
def sample_google_member_data():
    """Sample Google Workspace member data for tests."""
    return {
        "email": "user@company.com",
        "id": "member-123",
        "role": "MEMBER",
        "type": "USER",
    }


@pytest.fixture
def sample_aws_group_data():
    """Sample AWS Identity Store group data for tests."""
    return {
        "GroupId": "arn:aws:identitystore::123456789:group/12345",
        "DisplayName": "developers",
        "Description": "Development team",
    }


@pytest.fixture
def sample_aws_member_data():
    """Sample AWS Identity Store member data for tests."""
    return {
        "MemberId": "arn:aws:identitystore::123456789:user/12345",
        "MembershipType": "GROUP",
    }


@pytest.fixture
def provider_capabilities_factory():
    """Factory for creating ProviderCapabilities instances with custom values."""

    def _factory(
        supports_user_creation=False,
        supports_user_deletion=False,
        supports_group_creation=False,
        supports_group_deletion=False,
        supports_member_management=True,
        is_primary=False,
        provides_role_info=False,
        supports_batch_operations=False,
        max_batch_size=1,
    ):
        return ProviderCapabilities(
            supports_user_creation=supports_user_creation,
            supports_user_deletion=supports_user_deletion,
            supports_group_creation=supports_group_creation,
            supports_group_deletion=supports_group_deletion,
            supports_member_management=supports_member_management,
            is_primary=is_primary,
            provides_role_info=provides_role_info,
            supports_batch_operations=supports_batch_operations,
            max_batch_size=max_batch_size,
        )

    return _factory


@pytest.fixture
def operation_result_factory():
    """Factory for creating OperationResult instances."""

    def _factory(
        status=OperationStatus.SUCCESS,
        message="ok",
        data=None,
        error_code=None,
        retry_after=None,
    ):
        return OperationResult(
            status=status,
            message=message,
            data=data,
            error_code=error_code,
            retry_after=retry_after,
        )

    return _factory


# ============================================================================
# DUAL-REGISTRY TESTING FIXTURES (Feature-Level Pattern)
# ============================================================================


@pytest.fixture
def mock_settings_groups():
    """Mock core.config.settings with groups configuration.

    Returns a SimpleNamespace mimicking settings structure with groups attribute
    containing circuit breaker config and empty providers dict.
    """
    return types.SimpleNamespace(
        groups=types.SimpleNamespace(
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_timeout_seconds=60,
            circuit_breaker_half_open_max_calls=3,
            providers={},
        )
    )


@pytest.fixture
def mock_settings_groups_disabled_cb():
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
def patch_provider_base_settings(
    monkeypatch, mock_settings_groups
):  # pylint: disable=redefined-outer-name
    """Patch settings import in provider base module.

    Simplifies provider instantiation in tests by avoiding circuit breaker setup.
    """
    monkeypatch.setattr(
        "modules.groups.providers.base.settings",
        mock_settings_groups,
        raising=False,
    )


@pytest.fixture
def mock_provider_config():
    """Factory for creating provider configuration dicts."""

    def _factory(
        provider_name: str,
        enabled: bool = True,
        is_primary: bool = False,
        prefix: Optional[str] = None,
        capabilities: Optional[dict] = None,
    ) -> dict:
        config: dict = {"enabled": enabled}

        if is_primary:
            config["is_primary"] = True

        if prefix:
            config["prefix"] = prefix

        if capabilities:
            config["capabilities"] = capabilities

        return {provider_name: config}

    return _factory


@pytest.fixture
def single_primary_config(mock_provider_config):  # pylint: disable=redefined-outer-name
    """Provider configuration with single enabled primary provider."""
    return mock_provider_config(
        provider_name="google",
        enabled=True,
        is_primary=True,
        capabilities={
            "supports_member_management": True,
            "provides_role_info": True,
        },
    )


@pytest.fixture
def multi_provider_config(mock_provider_config):  # pylint: disable=redefined-outer-name
    """Provider configuration with primary and secondary providers."""
    google_cfg = mock_provider_config(
        provider_name="google",
        enabled=True,
        is_primary=True,
        capabilities={
            "supports_member_management": True,
            "provides_role_info": True,
        },
    )

    aws_cfg = mock_provider_config(
        provider_name="aws",
        enabled=True,
        is_primary=False,
        prefix="aws",
        capabilities={
            "supports_member_management": True,
            "supports_batch_operations": True,
            "max_batch_size": 100,
        },
    )

    return {**google_cfg, **aws_cfg}


class MockPrimaryGroupProvider(PrimaryGroupProvider):
    """Mock PrimaryGroupProvider for testing registry patterns."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize with optional config."""
        self._config = config or {}
        self.name = None
        self._prefix = None
        self._circuit_breaker = None
        self._capability_override = None

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return mock capabilities."""
        return ProviderCapabilities(
            is_primary=True,
            provides_role_info=True,
            supports_member_management=True,
        )

    def get_capabilities(self) -> ProviderCapabilities:
        """Get effective capabilities."""
        override = getattr(self, "_capability_override", None)
        return override if override is not None else self.capabilities

    @property
    def prefix(self) -> str:
        """Return provider prefix."""
        override = getattr(self, "_prefix", None)
        if override:
            return str(override)
        name = getattr(self, "name", None)
        if name:
            return str(name)
        return self.__class__.__name__.lower()

    def add_member(self, group_key: str, member_email: str) -> OperationResult:
        """Mock add member."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"added": True},
        )

    def remove_member(self, group_key: str, member_email: str) -> OperationResult:
        """Mock remove member."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"removed": True},
        )

    def list_groups(self) -> OperationResult:
        """Mock list groups."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"groups": []},
        )

    def get_group_members(self, group_key: str) -> OperationResult:
        """Mock get group members."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"members": []},
        )

    def validate_permissions(
        self, user_key: str, group_key: str, action: str
    ) -> OperationResult:
        """Mock validate permissions."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"allowed": True},
        )

    def health_check(self) -> OperationResult:
        """Mock health check."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"healthy": True},
        )

    # Implement required abstract methods from GroupProvider/PrimaryGroupProvider
    def _list_groups_impl(self, user_key: str) -> OperationResult:
        """Mock list groups implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"groups": []},
        )

    def _list_groups_with_members_impl(self, user_key: str) -> OperationResult:
        """Mock list groups with members implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"groups": []},
        )

    def _get_group_members_impl(self, group_key: str, **kwargs) -> OperationResult:
        """Mock get group members implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"members": []},
        )

    def _add_member_impl(self, group_key: str, member_email: str) -> OperationResult:
        """Mock add member implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"added": True},
        )

    def _remove_member_impl(self, group_key: str, member_email: str) -> OperationResult:
        """Mock remove member implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"removed": True},
        )

    def _validate_permissions_impl(
        self, user_key: str, group_key: str, action: str
    ) -> OperationResult:
        """Mock validate permissions implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"allowed": True},
        )

    def _health_check_impl(self) -> OperationResult:
        """Mock health check implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"healthy": True},
        )

    def _is_manager_impl(self, user_key: str, group_key: str) -> OperationResult:
        """Mock is manager implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"is_manager": False},
        )


class MockGroupProvider(GroupProvider):
    """Mock GroupProvider (secondary) for testing registry patterns."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize with optional config."""
        self._config = config or {}
        self.name = None
        self._prefix = None
        self._circuit_breaker = None
        self._capability_override = None

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return mock capabilities."""
        return ProviderCapabilities(
            is_primary=False,
            provides_role_info=False,
            supports_member_management=True,
        )

    def get_capabilities(self) -> ProviderCapabilities:
        """Get effective capabilities."""
        override = getattr(self, "_capability_override", None)
        return override if override is not None else self.capabilities

    @property
    def prefix(self) -> str:
        """Return provider prefix."""
        override = getattr(self, "_prefix", None)
        if override:
            return str(override)
        name = getattr(self, "name", None)
        if name:
            return str(name)
        return self.__class__.__name__.lower()

    def add_member(self, group_key: str, member_email: str) -> OperationResult:
        """Mock add member."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"added": True},
        )

    def remove_member(self, group_key: str, member_email: str) -> OperationResult:
        """Mock remove member."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"removed": True},
        )

    def list_groups(self) -> OperationResult:
        """Mock list groups."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"groups": []},
        )

    def get_group_members(self, group_key: str) -> OperationResult:
        """Mock get group members."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"members": []},
        )

    def health_check(self) -> OperationResult:
        """Mock health check."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"healthy": True},
        )

    # Implement required abstract methods from GroupProvider
    def _list_groups_impl(self, user_key: str) -> OperationResult:
        """Mock list groups implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"groups": []},
        )

    def _list_groups_with_members_impl(self, user_key: str) -> OperationResult:
        """Mock list groups with members implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"groups": []},
        )

    def _get_group_members_impl(self, group_key: str, **kwargs) -> OperationResult:
        """Mock get group members implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"members": []},
        )

    def _add_member_impl(self, group_key: str, member_email: str) -> OperationResult:
        """Mock add member implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"added": True},
        )

    def _remove_member_impl(self, group_key: str, member_email: str) -> OperationResult:
        """Mock remove member implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"removed": True},
        )

    def _validate_permissions_impl(
        self, user_key: str, group_key: str, action: str
    ) -> OperationResult:
        """Mock validate permissions implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"allowed": True},
        )

    def _health_check_impl(self) -> OperationResult:
        """Mock health check implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"healthy": True},
        )

    def _is_manager_impl(self, user_key: str, group_key: str) -> OperationResult:
        """Mock is manager implementation."""
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"is_manager": False},
        )


@pytest.fixture
def mock_primary_class():
    """Mock PrimaryGroupProvider class for provider registration."""
    return MockPrimaryGroupProvider


@pytest.fixture
def mock_secondary_class():
    """Mock GroupProvider class for secondary provider registration."""
    return MockGroupProvider
