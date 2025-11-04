"""Unit test fixtures for groups providers."""

import pytest
import types
from modules.groups.providers.base import (
    ProviderCapabilities,
    OperationResult,
    OperationStatus,
)


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
