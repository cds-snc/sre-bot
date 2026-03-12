"""Unit tests for GoogleDirectoryProvider."""

from unittest.mock import MagicMock

import pytest

from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.operations import OperationResult
from infrastructure.operations.status import OperationStatus


@pytest.fixture
def mock_google_clients():
    """Factory for GoogleWorkspaceClients mock with a stubbed directory client."""
    clients = MagicMock()
    clients.directory = MagicMock()
    return clients


@pytest.fixture
def provider(mock_google_clients):
    """GoogleDirectoryProvider backed by mocked clients."""
    return GoogleDirectoryProvider(google_clients=mock_google_clients)


class TestWarmup:
    def test_warmup_returns_success_when_list_groups_succeeds(
        self, provider, mock_google_clients
    ):
        # Arrange
        mock_google_clients.directory.list_groups.return_value = (
            OperationResult.success(data=[])
        )

        # Act
        result = provider.warmup()

        # Assert
        assert result.is_success
        mock_google_clients.directory.list_groups.assert_called_once_with(maxResults=1)

    def test_warmup_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_groups.return_value = (
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
        mock_google_clients.directory.list_groups.assert_not_called()
        mock_google_clients.directory.list_members.assert_not_called()


class TestGetGroupMembers:
    def test_returns_members_for_group(self, provider, mock_google_clients):
        # Arrange
        members = [{"email": "user@example.com"}, {"email": "admin@example.com"}]
        mock_google_clients.directory.list_members.return_value = (
            OperationResult.success(data=members)
        )

        # Act
        result = provider.get_group_members("sg-admin@example.com")

        # Assert
        assert result.is_success
        assert result.data == members
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
        assert result.data == {"is_member": True}

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
        assert result.data == {"is_member": False}

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
        assert result.data == {"is_member": False}

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
        assert result.data == {"is_member": True}

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
        assert result.data == {"is_member": False}


class TestListGroups:
    def test_delegates_to_directory_with_query(self, provider, mock_google_clients):
        # Arrange
        groups = [{"email": "sg-admin@example.com"}, {"email": "sg-devs@example.com"}]
        mock_google_clients.directory.list_groups.return_value = (
            OperationResult.success(data=groups)
        )

        # Act
        result = provider.list_groups(query="sg-")

        # Assert
        assert result.is_success
        assert result.data == groups
        mock_google_clients.directory.list_groups.assert_called_once_with(query="sg-")

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
