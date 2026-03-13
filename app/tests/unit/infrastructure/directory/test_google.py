"""Unit tests for GoogleDirectoryProvider."""

from unittest.mock import MagicMock

import pytest

from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
)
from infrastructure.operations import OperationResult
from infrastructure.operations.status import OperationStatus


@pytest.fixture
def mock_google_clients():
    """Factory for GoogleWorkspaceClients mock with a stubbed directory client."""
    clients = MagicMock()
    clients.directory = MagicMock()
    return clients


@pytest.fixture
def mock_directory_settings():
    """Directory settings fixture for provider construction."""
    settings = MagicMock()
    settings.managed_group_domain = "example.com"
    settings.enforce_managed_group_email = True
    return settings


@pytest.fixture
def provider(mock_google_clients, mock_directory_settings):
    """GoogleDirectoryProvider backed by mocked clients."""
    return GoogleDirectoryProvider(
        google_clients=mock_google_clients,
        directory_settings=mock_directory_settings,
    )


class TestWarmup:
    def test_warmup_returns_success_when_health_check_succeeds(
        self, provider, mock_google_clients
    ):
        # Arrange
        mock_google_clients.directory.health_check.return_value = (
            OperationResult.success(data=[])
        )

        # Act
        result = provider.warmup()

        # Assert
        assert result.is_success
        mock_google_clients.directory.health_check.assert_called_once_with()

    def test_warmup_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.health_check.return_value = (
            OperationResult.permanent_error("credentials_invalid")
        )

        # Act
        result = provider.warmup()

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR


class TestHealthCheck:
    def test_health_check_always_returns_success(self, provider):
        # Act
        result = provider.health_check()

        # Assert
        assert result.is_success

    def test_health_check_does_not_call_directory_api(
        self, provider, mock_google_clients
    ):
        # Act
        provider.health_check()

        # Assert
        mock_google_clients.directory.health_check.assert_not_called()
        mock_google_clients.directory.list_members.assert_not_called()


class TestGetUser:
    def test_returns_canonical_user(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.get_user.return_value = OperationResult.success(
            data={
                "primaryEmail": "USER@EXAMPLE.COM",
                "id": "user-123",
                "name": {"fullName": "Test User"},
                "suspended": False,
            }
        )

        # Act
        result = provider.get_user("USER@EXAMPLE.COM")

        # Assert
        assert result.is_success
        assert result.data == {
            "user": DirectoryUser(
                email="user@example.com",
                provider_user_id="user-123",
                display_name="Test User",
                is_active=True,
                provider="google",
            )
        }
        mock_google_clients.directory.get_user.assert_called_once_with(
            "user@example.com"
        )

    def test_propagates_get_user_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.get_user.return_value = (
            OperationResult.permanent_error("user_not_found")
        )

        # Act
        result = provider.get_user("user@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR


class TestListUsers:
    def test_returns_canonical_users_for_query(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_users.return_value = OperationResult.success(
            data=[
                {
                    "primaryEmail": "USER1@EXAMPLE.COM",
                    "id": "user-1",
                    "name": {"fullName": "User One"},
                },
                {
                    "primaryEmail": "user2@example.com",
                    "id": "user-2",
                    "name": {"fullName": "User Two"},
                    "suspended": True,
                },
            ]
        )

        # Act
        result = provider.list_users(query="name:User", limit=1)

        # Assert
        assert result.is_success
        assert result.data == {
            "users": [
                DirectoryUser(
                    email="user1@example.com",
                    provider_user_id="user-1",
                    display_name="User One",
                    is_active=None,
                    provider="google",
                )
            ]
        }
        mock_google_clients.directory.list_users.assert_called_once_with(
            maxResults=1,
            query="name:User",
        )

    def test_returns_empty_list_when_limit_is_non_positive(self, provider):
        # Act
        result = provider.list_users(limit=0)

        # Assert
        assert result.is_success
        assert result.data == {"users": []}

    def test_propagates_list_users_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_users.return_value = (
            OperationResult.transient_error("directory_unavailable")
        )

        # Act
        result = provider.list_users(query="email:user")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR


class TestGetGroupMembers:
    def test_returns_canonical_members_for_group(self, provider, mock_google_clients):
        # Arrange
        members = [
            {"email": "user@example.com", "id": "1", "role": "MEMBER"},
            {"email": "admin@example.com", "id": "2", "role": "OWNER"},
        ]
        mock_google_clients.directory.list_members.return_value = (
            OperationResult.success(data=members)
        )

        # Act
        result = provider.get_group_members("sg-admin@example.com")

        # Assert
        assert result.is_success
        assert result.data == {
            "members": [
                DirectoryMember(
                    email="user@example.com",
                    membership_id="1",
                    provider_user_id=None,
                    role="MEMBER",
                    provider="google",
                ),
                DirectoryMember(
                    email="admin@example.com",
                    membership_id="2",
                    provider_user_id=None,
                    role="OWNER",
                    provider="google",
                ),
            ]
        }
        mock_google_clients.directory.list_members.assert_called_once_with(
            "sg-admin@example.com"
        )

    def test_normalises_group_key_to_lowercase(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_members.return_value = (
            OperationResult.success(data=[])
        )

        # Act
        provider.get_group_members("SG-ADMIN@EXAMPLE.COM")

        # Assert
        mock_google_clients.directory.list_members.assert_called_once_with(
            "sg-admin@example.com"
        )

    def test_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_members.return_value = (
            OperationResult.transient_error("rate_limited")
        )

        # Act
        result = provider.get_group_members("sg-admin@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR


class TestCheckMembership:
    def test_returns_true_when_user_is_member(self, provider, mock_google_clients):
        # Arrange
        members = [
            {"email": "member@example.com"},
            {"email": "other@example.com"},
        ]
        mock_google_clients.directory.list_members.return_value = (
            OperationResult.success(data=members)
        )

        # Act
        result = provider.check_membership("sg-team@example.com", "member@example.com")

        # Assert
        assert result.is_success
        assert result.data == {
            "membership": MembershipCheckResult(
                group_email="sg-team@example.com",
                group_slug="sg-team",
                provider_group_id=None,
                user_email="member@example.com",
                is_member=True,
            )
        }

    def test_returns_false_when_user_is_not_member(self, provider, mock_google_clients):
        # Arrange
        members = [{"email": "other@example.com"}]
        mock_google_clients.directory.list_members.return_value = (
            OperationResult.success(data=members)
        )

        # Act
        result = provider.check_membership("sg-team@example.com", "absent@example.com")

        # Assert
        assert result.is_success
        assert result.data == {
            "membership": MembershipCheckResult(
                group_email="sg-team@example.com",
                group_slug="sg-team",
                provider_group_id=None,
                user_email="absent@example.com",
                is_member=False,
            )
        }

    def test_returns_false_when_member_list_is_empty(
        self, provider, mock_google_clients
    ):
        # Arrange
        mock_google_clients.directory.list_members.return_value = (
            OperationResult.success(data=[])
        )

        # Act
        result = provider.check_membership("sg-empty@example.com", "user@example.com")

        # Assert
        assert result.is_success
        assert result.data == {
            "membership": MembershipCheckResult(
                group_email="sg-empty@example.com",
                group_slug="sg-empty",
                provider_group_id=None,
                user_email="user@example.com",
                is_member=False,
            )
        }

    def test_comparison_is_case_insensitive(self, provider, mock_google_clients):
        # Arrange
        members = [{"email": "MEMBER@EXAMPLE.COM"}]
        mock_google_clients.directory.list_members.return_value = (
            OperationResult.success(data=members)
        )

        # Act
        result = provider.check_membership("sg-team@example.com", "member@example.com")

        # Assert
        assert result.is_success
        assert result.data == {
            "membership": MembershipCheckResult(
                group_email="sg-team@example.com",
                group_slug="sg-team",
                provider_group_id=None,
                user_email="member@example.com",
                is_member=True,
            )
        }

    def test_normalises_group_key_to_lowercase(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_members.return_value = (
            OperationResult.success(data=[])
        )

        # Act
        provider.check_membership("SG-TEAM@EXAMPLE.COM", "user@example.com")

        # Assert
        mock_google_clients.directory.list_members.assert_called_once_with(
            "sg-team@example.com"
        )

    def test_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_members.return_value = (
            OperationResult.permanent_error("group_not_found")
        )

        # Act
        result = provider.check_membership("sg-ghost@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR

    def test_handles_none_data_from_list_members(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_members.return_value = (
            OperationResult.success(data=None)
        )

        # Act
        result = provider.check_membership("sg-team@example.com", "user@example.com")

        # Assert
        assert result.is_success
        assert result.data == {
            "membership": MembershipCheckResult(
                group_email="sg-team@example.com",
                group_slug="sg-team",
                provider_group_id=None,
                user_email="user@example.com",
                is_member=False,
            )
        }


class TestListGroups:
    def test_returns_canonical_groups_for_query(self, provider, mock_google_clients):
        # Arrange
        groups = [
            {
                "email": "sg-admin@example.com",
                "id": "group-1",
                "name": "Admins",
                "description": "Admin group",
            },
            {
                "email": "sg-devs@example.com",
                "id": "group-2",
                "name": "Developers",
                "description": "Dev group",
            },
        ]
        mock_google_clients.directory.list_groups.return_value = (
            OperationResult.success(data=groups)
        )

        # Act
        result = provider.list_groups(query="sg-")

        # Assert
        assert result.is_success
        assert result.data == {
            "groups": [
                DirectoryGroup(
                    group_email="sg-admin@example.com",
                    group_slug="sg-admin",
                    provider_group_id="group-1",
                    name="Admins",
                    description="Admin group",
                    provider="google",
                ),
                DirectoryGroup(
                    group_email="sg-devs@example.com",
                    group_slug="sg-devs",
                    provider_group_id="group-2",
                    name="Developers",
                    description="Dev group",
                    provider="google",
                ),
            ]
        }
        mock_google_clients.directory.list_groups.assert_called_once_with(query="sg-")

    def test_returns_error_when_group_email_is_missing(
        self, provider, mock_google_clients
    ):
        # Arrange
        mock_google_clients.directory.list_groups.return_value = (
            OperationResult.success(data=[{"id": "group-1", "name": "Admins"}])
        )

        # Act
        result = provider.list_groups(query="sg-")

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_GROUP_EMAIL_REQUIRED"

    def test_returns_error_when_managed_group_domain_mismatches(
        self, provider, mock_google_clients
    ):
        # Arrange
        mock_google_clients.directory.list_groups.return_value = (
            OperationResult.success(
                data=[
                    {
                        "email": "sg-admin@other.example",
                        "id": "group-1",
                        "name": "Admins",
                    }
                ]
            )
        )

        # Act
        result = provider.list_groups(query="sg-")

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_GROUP_DOMAIN_MISMATCH"

    def test_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_groups.return_value = (
            OperationResult.transient_error("service_unavailable")
        )

        # Act
        result = provider.list_groups(query="sg-")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR
