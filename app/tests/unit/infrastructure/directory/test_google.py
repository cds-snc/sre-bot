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
    settings.managed_group_prefix = "sg-"
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
    def test_warmup_returns_success_when_health_check_succeeds(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.health_check.return_value = OperationResult.success(data=[])

        # Act
        result = provider.warmup()

        # Assert
        assert result.is_success
        mock_google_clients.directory.health_check.assert_called_once_with()

    def test_warmup_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.health_check.return_value = OperationResult.permanent_error("credentials_invalid")

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

    def test_health_check_does_not_call_directory_api(self, provider, mock_google_clients):
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
        assert result.data == DirectoryUser(
            email="user@example.com",
            provider_user_id="user-123",
            display_name="Test User",
            is_active=True,
            provider="google",
        )
        mock_google_clients.directory.get_user.assert_called_once_with("user@example.com")

    def test_falls_back_to_email_list_and_name_parts(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.get_user.return_value = OperationResult.success(
            data={
                "id": "user-456",
                "emails": [
                    {"address": "USER.ALIAS@EXAMPLE.COM", "primary": True},
                ],
                "name": {
                    "givenName": "Alias",
                    "familyName": "User",
                },
            }
        )

        # Act
        result = provider.get_user("user.alias@example.com")

        # Assert
        assert result.is_success
        assert result.data == DirectoryUser(
            email="user.alias@example.com",
            provider_user_id="user-456",
            display_name="Alias User",
            is_active=None,
            provider="google",
        )

    def test_propagates_get_user_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.get_user.return_value = OperationResult.permanent_error("user_not_found")

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
        assert result.data == [
            DirectoryUser(
                email="user1@example.com",
                provider_user_id="user-1",
                display_name="User One",
                is_active=None,
                provider="google",
            )
        ]
        mock_google_clients.directory.list_users.assert_called_once_with(
            maxResults=1,
            query="name:User",
        )

    def test_returns_empty_list_when_limit_is_non_positive(self, provider):
        # Act
        result = provider.list_users(limit=0)

        # Assert
        assert result.is_success
        assert result.data == []

    def test_propagates_list_users_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_users.return_value = OperationResult.transient_error("directory_unavailable")

        # Act
        result = provider.list_users(query="email:user")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR


class TestGetGroupMembers:
    def test_returns_canonical_members_for_group(self, provider, mock_google_clients):
        # Arrange
        members = [
            {
                "email": "user@example.com",
                "id": "1",
                "role": "MEMBER",
                "type": "USER",
            },
            {
                "email": "admin@example.com",
                "id": "2",
                "role": "OWNER",
                "type": "USER",
            },
        ]
        mock_google_clients.directory.list_members.return_value = OperationResult.success(data=members)

        # Act
        result = provider.get_group_members("sg-admin@example.com")

        # Assert
        assert result.is_success
        assert result.data == [
            DirectoryMember(
                email="user@example.com",
                membership_id="1",
                provider_user_id=None,
                member_type="USER",
                role="MEMBER",
                provider="google",
            ),
            DirectoryMember(
                email="admin@example.com",
                membership_id="2",
                provider_user_id=None,
                member_type="USER",
                role="OWNER",
                provider="google",
            ),
        ]
        mock_google_clients.directory.list_members.assert_called_once_with(
            "sg-admin@example.com",
            includeDerivedMembership=True,
        )

    def test_returns_all_member_types_by_default(self, provider, mock_google_clients):
        # Arrange
        members = [
            {
                "email": "user@example.com",
                "id": "1",
                "role": "MEMBER",
                "type": "USER",
            },
            {
                "email": "sg-child@example.com",
                "id": "2",
                "role": "MEMBER",
                "type": "GROUP",
            },
        ]
        mock_google_clients.directory.list_members.return_value = OperationResult.success(data=members)

        # Act
        result = provider.get_group_members("sg-admin@example.com")

        # Assert
        assert result.is_success
        assert result.data == [
            DirectoryMember(
                email="user@example.com",
                membership_id="1",
                provider_user_id=None,
                member_type="USER",
                role="MEMBER",
                provider="google",
            ),
            DirectoryMember(
                email="sg-child@example.com",
                membership_id="2",
                provider_user_id=None,
                member_type="GROUP",
                role="MEMBER",
                provider="google",
            ),
        ]

    def test_filters_to_requested_member_types(self, provider, mock_google_clients):
        # Arrange
        members = [
            {
                "email": "user@example.com",
                "id": "1",
                "role": "MEMBER",
                "type": "USER",
            },
            {
                "email": "sg-child@example.com",
                "id": "2",
                "role": "MEMBER",
                "type": "GROUP",
            },
        ]
        mock_google_clients.directory.list_members.return_value = OperationResult.success(data=members)

        # Act
        result = provider.get_group_members(
            "sg-admin@example.com",
            include_member_types={"USER"},
        )

        # Assert
        assert result.is_success
        assert result.data == [
            DirectoryMember(
                email="user@example.com",
                membership_id="1",
                provider_user_id=None,
                member_type="USER",
                role="MEMBER",
                provider="google",
            ),
        ]

    def test_can_include_group_members_when_requested(self, provider, mock_google_clients):
        # Arrange
        members = [
            {
                "email": "user@example.com",
                "id": "1",
                "role": "MEMBER",
                "type": "USER",
            },
            {
                "email": "sg-child@example.com",
                "id": "2",
                "role": "MEMBER",
                "type": "GROUP",
            },
        ]
        mock_google_clients.directory.list_members.return_value = OperationResult.success(data=members)

        # Act
        result = provider.get_group_members(
            "sg-admin@example.com",
            include_member_types={"GROUP"},
        )

        # Assert
        assert result.is_success
        assert result.data == [
            DirectoryMember(
                email="sg-child@example.com",
                membership_id="2",
                provider_user_id=None,
                member_type="GROUP",
                role="MEMBER",
                provider="google",
            )
        ]

    def test_uses_primary_email_when_member_email_is_missing(self, provider, mock_google_clients):
        # Arrange
        members = [
            {
                "primaryEmail": "USER@EXAMPLE.COM",
                "id": "1",
                "role": "MEMBER",
                "type": "USER",
            },
            {"id": "2", "role": "OWNER"},
        ]
        mock_google_clients.directory.list_members.return_value = OperationResult.success(data=members)

        # Act
        result = provider.get_group_members("sg-admin@example.com")

        # Assert
        assert result.is_success
        assert result.data == [
            DirectoryMember(
                email="user@example.com",
                membership_id="1",
                provider_user_id=None,
                member_type="USER",
                role="MEMBER",
                provider="google",
            ),
        ]

    def test_normalises_group_key_to_lowercase(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_members.return_value = OperationResult.success(data=[])

        # Act
        provider.get_group_members("SG-ADMIN@EXAMPLE.COM")

        # Assert
        mock_google_clients.directory.list_members.assert_called_once_with(
            "sg-admin@example.com",
            includeDerivedMembership=True,
        )

    def test_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_members.return_value = OperationResult.transient_error("rate_limited")

        # Act
        result = provider.get_group_members("sg-admin@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR

    def test_composes_group_email_from_slug(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_members.return_value = OperationResult.success(data=[])

        # Act
        provider.get_group_members("sg-admin")

        # Assert
        mock_google_clients.directory.list_members.assert_called_once_with(
            "sg-admin@example.com",
            includeDerivedMembership=True,
        )


class TestGetGroup:
    def test_returns_canonical_group(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.get_group.return_value = OperationResult.success(
            data={
                "email": "SG-ADMIN@EXAMPLE.COM",
                "id": "group-1",
                "name": "Admins",
                "description": "Admin group",
            }
        )

        # Act
        result = provider.get_group("SG-ADMIN@EXAMPLE.COM")

        # Assert
        assert result.is_success
        assert result.data == DirectoryGroup(
            group_email="sg-admin@example.com",
            group_slug="sg-admin",
            provider_group_id="group-1",
            name="Admins",
            description="Admin group",
            provider="google",
        )
        mock_google_clients.directory.get_group.assert_called_once_with("sg-admin@example.com")

    def test_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.get_group.return_value = OperationResult.error(
            OperationStatus.NOT_FOUND,
            "group_not_found",
        )

        # Act
        result = provider.get_group("sg-ghost@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.NOT_FOUND

    def test_returns_error_when_group_payload_is_not_dict(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.get_group.return_value = OperationResult.success(data=[])

        # Act
        result = provider.get_group("sg-admin@example.com")

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_GROUP_PAYLOAD_INVALID"


class TestAddGroupMember:
    def test_adds_member_and_returns_canonical_member(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.add_member.return_value = OperationResult.success(
            data={
                "email": "USER@EXAMPLE.COM",
                "id": "member-1",
                "role": "OWNER",
            }
        )

        # Act
        result = provider.add_group_member("SG-ADMIN@EXAMPLE.COM", "USER@EXAMPLE.COM", role="owner")

        # Assert
        assert result.is_success
        assert result.data == DirectoryMember(
            email="user@example.com",
            membership_id="member-1",
            provider_user_id=None,
            role="OWNER",
            provider="google",
        )
        mock_google_clients.directory.add_member.assert_called_once_with(
            "sg-admin@example.com",
            body={
                "email": "user@example.com",
                "role": "OWNER",
            },
        )

    def test_falls_back_to_requested_role_when_payload_role_missing(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.add_member.return_value = OperationResult.success(
            data={
                "email": "user@example.com",
                "id": "member-2",
            }
        )

        # Act
        result = provider.add_group_member("sg-admin@example.com", "user@example.com", role="member")

        # Assert
        assert result.is_success
        assert result.data == DirectoryMember(
            email="user@example.com",
            membership_id="member-2",
            provider_user_id=None,
            role="MEMBER",
            provider="google",
        )

    def test_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.add_member.return_value = OperationResult.transient_error("directory_unavailable")

        # Act
        result = provider.add_group_member("sg-admin@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR

    def test_returns_error_when_member_payload_is_not_dict(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.add_member.return_value = OperationResult.success(data=[])

        # Act
        result = provider.add_group_member("sg-admin@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_MEMBER_PAYLOAD_INVALID"

    def test_returns_error_when_member_email_missing(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.add_member.return_value = OperationResult.success(data={"id": "member-3"})

        # Act
        result = provider.add_group_member("sg-admin@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_MEMBER_EMAIL_REQUIRED"


class TestRemoveGroupMember:
    def test_removes_member_with_normalized_keys(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.remove_member.return_value = OperationResult.success()

        # Act
        result = provider.remove_group_member(
            "SG-ADMIN@EXAMPLE.COM",
            "USER@EXAMPLE.COM",
        )

        # Assert
        assert result.is_success
        assert result.data is None
        mock_google_clients.directory.remove_member.assert_called_once_with(
            "sg-admin@example.com",
            "user@example.com",
        )

    def test_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.remove_member.return_value = OperationResult.transient_error("directory_unavailable")

        # Act
        result = provider.remove_group_member("sg-admin@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR


class TestCheckMembership:
    def test_returns_true_when_user_is_member(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.has_member.return_value = OperationResult.success(data={"isMember": True})

        # Act
        result = provider.check_membership("sg-team@example.com", "member@example.com")

        # Assert
        assert result.is_success
        assert result.data == MembershipCheckResult(
            group_email="sg-team@example.com",
            group_slug="sg-team",
            provider_group_id=None,
            user_email="member@example.com",
            is_member=True,
        )

    def test_returns_false_when_user_is_not_member(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.has_member.return_value = OperationResult.success(data={"isMember": False})

        # Act
        result = provider.check_membership("sg-team@example.com", "absent@example.com")

        # Assert
        assert result.is_success
        assert result.data == MembershipCheckResult(
            group_email="sg-team@example.com",
            group_slug="sg-team",
            provider_group_id=None,
            user_email="absent@example.com",
            is_member=False,
        )

    def test_returns_false_when_not_a_member(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.has_member.return_value = OperationResult.success(data={"isMember": False})

        # Act
        result = provider.check_membership("sg-empty@example.com", "user@example.com")

        # Assert
        assert result.is_success
        assert result.data == MembershipCheckResult(
            group_email="sg-empty@example.com",
            group_slug="sg-empty",
            provider_group_id=None,
            user_email="user@example.com",
            is_member=False,
        )

    def test_normalises_group_key_and_email_to_lowercase(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.has_member.return_value = OperationResult.success(data={"isMember": False})

        # Act
        provider.check_membership("SG-TEAM@EXAMPLE.COM", "USER@EXAMPLE.COM")

        # Assert
        mock_google_clients.directory.has_member.assert_called_once_with("sg-team@example.com", "user@example.com")

    def test_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.has_member.return_value = OperationResult.permanent_error("group_not_found")

        # Act
        result = provider.check_membership("sg-ghost@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR

    def test_returns_error_when_has_member_payload_is_not_dict(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.has_member.return_value = OperationResult.success(data=None)

        # Act
        result = provider.check_membership("sg-team@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_MEMBERSHIP_PAYLOAD_INVALID"


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
        mock_google_clients.directory.list_groups.return_value = OperationResult.success(data=groups)

        # Act
        result = provider.list_groups(query="sg-")

        # Assert
        assert result.is_success
        assert result.data == [
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
        mock_google_clients.directory.list_groups.assert_called_once_with()

    def test_uses_group_alias_fields_when_standard_keys_are_missing(self, provider, mock_google_clients):
        # Arrange
        groups = [
            {
                "groupEmail": "SG-OPS@EXAMPLE.COM",
                "groupId": "group-9",
                "displayName": "Ops",
            }
        ]
        mock_google_clients.directory.list_groups.return_value = OperationResult.success(data=groups)

        # Act
        result = provider.list_groups(query="email:sg-*")

        # Assert
        assert result.is_success
        mock_google_clients.directory.list_groups.assert_called_once_with()
        assert result.data == [
            DirectoryGroup(
                group_email="sg-ops@example.com",
                group_slug="sg-ops",
                provider_group_id="group-9",
                name="Ops",
                description=None,
                provider="google",
            ),
        ]

    def test_prefers_managed_alias_when_primary_email_uses_old_pattern(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_groups.return_value = OperationResult.success(
            data=[
                {
                    "email": "aws-finops@example.com",
                    "aliases": ["sg-aws-finops@example.com"],
                    "id": "group-10",
                    "name": "FinOps",
                }
            ]
        )

        # Act
        result = provider.list_groups(query="sg-aws-")

        # Assert
        assert result.is_success
        mock_google_clients.directory.list_groups.assert_called_once_with()
        assert result.data == [
            DirectoryGroup(
                group_email="sg-aws-finops@example.com",
                group_slug="sg-aws-finops",
                provider_group_id="group-10",
                name="FinOps",
                description=None,
                provider="google",
            )
        ]

    def test_skips_groups_when_email_is_missing_for_alias_aware_discovery(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_groups.return_value = OperationResult.success(
            data=[{"id": "group-1", "name": "Admins"}]
        )

        # Act
        result = provider.list_groups(query="sg-")

        # Assert
        assert result.is_success
        assert result.data == []
        mock_google_clients.directory.list_groups.assert_called_once_with()

    def test_returns_error_when_managed_group_domain_mismatches(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_groups.return_value = OperationResult.success(
            data=[
                {
                    "email": "platform-admins@other.example",
                    "id": "group-1",
                    "name": "Admins",
                }
            ]
        )

        # Act
        result = provider.list_groups(query="name:Admins")

        # Assert
        # name:Admins is a Google query expression — passed through unchanged
        mock_google_clients.directory.list_groups.assert_called_once_with(query="name:Admins")
        assert not result.is_success
        assert result.error_code == "DIRECTORY_GROUP_DOMAIN_MISMATCH"

    def test_propagates_directory_error(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.list_groups.return_value = OperationResult.transient_error("service_unavailable")

        # Act
        result = provider.list_groups(query="sg-")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR


class TestGetGroupMembersBatch:
    def test_returns_members_for_each_group(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.get_batch_group_members.return_value = OperationResult.success(
            data={
                "sg-aws-admin@example.com": [
                    {"email": "alice@example.com", "type": "USER", "id": "m1"},
                ],
                "sg-aws-read@example.com": [
                    {"email": "bob@example.com", "type": "USER", "id": "m2"},
                ],
            }
        )

        # Act
        result = provider.get_group_members_batch(
            ["sg-aws-admin@example.com", "sg-aws-read@example.com"],
            include_member_types={"USER"},
        )

        # Assert
        assert result.is_success
        assert set(result.data.keys()) == {
            "sg-aws-admin@example.com",
            "sg-aws-read@example.com",
        }
        assert len(result.data["sg-aws-admin@example.com"]) == 1
        assert result.data["sg-aws-admin@example.com"][0].email == "alice@example.com"
        assert len(result.data["sg-aws-read@example.com"]) == 1
        assert result.data["sg-aws-read@example.com"][0].email == "bob@example.com"

    def test_returns_empty_dict_for_empty_input(self, provider, mock_google_clients):
        # Act
        result = provider.get_group_members_batch([])

        # Assert
        assert result.is_success
        assert result.data == {}
        mock_google_clients.directory.get_batch_group_members.assert_not_called()

    def test_propagates_batch_failure(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.get_batch_group_members.return_value = OperationResult.transient_error(
            "batch_request_failed"
        )

        # Act
        result = provider.get_group_members_batch(["sg-aws-admin@example.com"])

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR

    def test_filters_to_requested_member_types(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.get_batch_group_members.return_value = OperationResult.success(
            data={
                "sg-aws-admin@example.com": [
                    {"email": "alice@example.com", "type": "USER", "id": "m1"},
                    {
                        "email": "nested-group@example.com",
                        "type": "GROUP",
                        "id": "m2",
                    },
                ],
            }
        )

        # Act
        result = provider.get_group_members_batch(
            ["sg-aws-admin@example.com"],
            include_member_types={"USER"},
        )

        # Assert
        assert result.is_success
        members = result.data["sg-aws-admin@example.com"]
        assert len(members) == 1
        assert members[0].email == "alice@example.com"

    def test_normalises_group_keys_to_lowercase(self, provider, mock_google_clients):
        # Arrange
        mock_google_clients.directory.get_batch_group_members.return_value = OperationResult.success(
            data={"sg-aws-admin@example.com": []}
        )

        # Act
        provider.get_group_members_batch(["SG-AWS-Admin@EXAMPLE.COM"])

        # Assert
        mock_google_clients.directory.get_batch_group_members.assert_called_once_with(["sg-aws-admin@example.com"])
