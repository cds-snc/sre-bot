"""Unit tests for GoogleDirectoryProvider."""

from typing import Any
from unittest.mock import MagicMock

import httplib2
import pytest
from googleapiclient.errors import HttpError

from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
)
from infrastructure.operations.status import OperationStatus


def _request(payload: Any) -> MagicMock:
    """Build a fake googleapiclient request whose execute() returns payload."""
    request = MagicMock()
    request.execute.return_value = payload
    return request


def _http_error(status: int) -> HttpError:
    """Build a fake googleapiclient HttpError carrying the given HTTP status."""
    return HttpError(httplib2.Response({"status": status}), b"{}")


def _install_fake_batch(service: MagicMock, responses: dict[str, Any]) -> None:
    """Configure new_batch_http_request to synchronously invoke callback per added request.

    Requests whose request_id is missing from responses invoke the callback
    with an exception, mirroring a per-item Admin SDK batch failure.
    """

    def new_batch_http_request(callback):
        added: list[tuple[str, Any]] = []
        batch = MagicMock()

        def add(request, request_id):
            added.append((request_id, request))

        def execute(**kwargs):
            for request_id, _request_obj in added:
                if request_id in responses:
                    callback(request_id, responses[request_id], None)
                else:
                    callback(request_id, None, RuntimeError(f"missing response for {request_id}"))

        batch.add.side_effect = add
        batch.execute.side_effect = execute
        return batch

    service.new_batch_http_request.side_effect = new_batch_http_request


@pytest.fixture
def google_service() -> MagicMock:
    """Fake Admin SDK Directory service with single-page list defaults."""
    service = MagicMock()
    service.users.return_value.list_next.return_value = None
    service.groups.return_value.list_next.return_value = None
    service.members.return_value.list_next.return_value = None
    return service


@pytest.fixture
def mock_directory_settings():
    """Directory settings fixture for provider construction."""
    settings = MagicMock()
    settings.managed_group_domain = "example.com"
    settings.managed_group_prefix = "sg-"
    settings.enforce_managed_group_email = True
    return settings


@pytest.fixture
def provider(google_service, mock_directory_settings):
    """GoogleDirectoryProvider backed by a fake Admin SDK Directory service."""
    return GoogleDirectoryProvider(
        get_service=lambda scopes: google_service,
        directory_settings=mock_directory_settings,
        customer_id="my_customer",
    )


class TestWarmup:
    def test_warmup_returns_success_when_health_check_succeeds(self, provider, google_service):
        # Arrange
        google_service.customers.return_value.get.return_value = _request({"id": "customer-1"})

        # Act
        result = provider.warmup()

        # Assert
        assert result.is_success
        google_service.customers.return_value.get.assert_called_once_with(customerKey="my_customer")

    def test_warmup_propagates_directory_error(self, provider, google_service):
        # Arrange
        google_service.customers.return_value.get.return_value.execute.side_effect = _http_error(401)

        # Act
        result = provider.warmup()

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.UNAUTHORIZED


class TestHealthCheck:
    def test_health_check_always_returns_success(self, provider):
        # Act
        result = provider.health_check()

        # Assert
        assert result.is_success

    def test_health_check_does_not_call_directory_api(self, provider, google_service):
        # Act
        provider.health_check()

        # Assert
        google_service.customers.assert_not_called()
        google_service.members.assert_not_called()


class TestGetUser:
    def test_returns_canonical_user(self, provider, google_service):
        # Arrange
        google_service.users.return_value.get.return_value = _request(
            {
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
        google_service.users.return_value.get.assert_called_once_with(userKey="user@example.com")

    def test_falls_back_to_email_list_and_name_parts(self, provider, google_service):
        # Arrange
        google_service.users.return_value.get.return_value = _request(
            {
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

    def test_propagates_get_user_error(self, provider, google_service):
        # Arrange
        google_service.users.return_value.get.return_value.execute.side_effect = _http_error(404)

        # Act
        result = provider.get_user("user@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.NOT_FOUND


class TestListUsers:
    def test_returns_canonical_users_for_query(self, provider, google_service):
        # Arrange
        google_service.users.return_value.list.return_value = _request(
            {
                "users": [
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
            }
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
        google_service.users.return_value.list.assert_called_once_with(
            customer="my_customer",
            maxResults=1,
            query="name:User",
        )

    def test_returns_empty_list_when_limit_is_non_positive(self, provider):
        # Act
        result = provider.list_users(limit=0)

        # Assert
        assert result.is_success
        assert result.data == []

    def test_propagates_list_users_error(self, provider, google_service):
        # Arrange
        google_service.users.return_value.list.return_value.execute.side_effect = _http_error(503)

        # Act
        result = provider.list_users(query="email:user")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR


class TestGetGroupMembers:
    def test_returns_canonical_members_for_group(self, provider, google_service):
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
        google_service.members.return_value.list.return_value = _request({"members": members})

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
        google_service.members.return_value.list.assert_called_once_with(
            groupKey="sg-admin@example.com",
            includeDerivedMembership=True,
        )

    def test_returns_all_member_types_by_default(self, provider, google_service):
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
        google_service.members.return_value.list.return_value = _request({"members": members})

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

    def test_filters_to_requested_member_types(self, provider, google_service):
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
        google_service.members.return_value.list.return_value = _request({"members": members})

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

    def test_can_include_group_members_when_requested(self, provider, google_service):
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
        google_service.members.return_value.list.return_value = _request({"members": members})

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

    def test_uses_primary_email_when_member_email_is_missing(self, provider, google_service):
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
        google_service.members.return_value.list.return_value = _request({"members": members})

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

    def test_normalises_group_key_to_lowercase(self, provider, google_service):
        # Arrange
        google_service.members.return_value.list.return_value = _request({"members": []})

        # Act
        provider.get_group_members("SG-ADMIN@EXAMPLE.COM")

        # Assert
        google_service.members.return_value.list.assert_called_once_with(
            groupKey="sg-admin@example.com",
            includeDerivedMembership=True,
        )

    def test_propagates_directory_error(self, provider, google_service):
        # Arrange
        google_service.members.return_value.list.return_value.execute.side_effect = _http_error(429)

        # Act
        result = provider.get_group_members("sg-admin@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR

    def test_composes_group_email_from_slug(self, provider, google_service):
        # Arrange
        google_service.members.return_value.list.return_value = _request({"members": []})

        # Act
        provider.get_group_members("sg-admin")

        # Assert
        google_service.members.return_value.list.assert_called_once_with(
            groupKey="sg-admin@example.com",
            includeDerivedMembership=True,
        )


class TestGetGroup:
    def test_returns_canonical_group(self, provider, google_service):
        # Arrange
        google_service.groups.return_value.get.return_value = _request(
            {
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
        google_service.groups.return_value.get.assert_called_once_with(groupKey="sg-admin@example.com")

    def test_propagates_directory_error(self, provider, google_service):
        # Arrange
        google_service.groups.return_value.get.return_value.execute.side_effect = _http_error(404)

        # Act
        result = provider.get_group("sg-ghost@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.NOT_FOUND

    def test_returns_error_when_group_payload_is_not_dict(self, provider, google_service):
        # Arrange
        google_service.groups.return_value.get.return_value = _request([])

        # Act
        result = provider.get_group("sg-admin@example.com")

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_GROUP_PAYLOAD_INVALID"


class TestAddGroupMember:
    def test_adds_member_and_returns_canonical_member(self, provider, google_service):
        # Arrange
        google_service.members.return_value.insert.return_value = _request(
            {
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
        google_service.members.return_value.insert.assert_called_once_with(
            groupKey="sg-admin@example.com",
            body={
                "email": "user@example.com",
                "role": "OWNER",
            },
        )

    def test_falls_back_to_requested_role_when_payload_role_missing(self, provider, google_service):
        # Arrange
        google_service.members.return_value.insert.return_value = _request(
            {
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

    def test_propagates_directory_error(self, provider, google_service):
        # Arrange
        google_service.members.return_value.insert.return_value.execute.side_effect = _http_error(503)

        # Act
        result = provider.add_group_member("sg-admin@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR

    def test_returns_error_when_member_payload_is_not_dict(self, provider, google_service):
        # Arrange
        google_service.members.return_value.insert.return_value = _request([])

        # Act
        result = provider.add_group_member("sg-admin@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_MEMBER_PAYLOAD_INVALID"

    def test_returns_error_when_member_email_missing(self, provider, google_service):
        # Arrange
        google_service.members.return_value.insert.return_value = _request({"id": "member-3"})

        # Act
        result = provider.add_group_member("sg-admin@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_MEMBER_EMAIL_REQUIRED"


class TestRemoveGroupMember:
    def test_removes_member_with_normalized_keys(self, provider, google_service):
        # Arrange
        google_service.members.return_value.delete.return_value = _request({})

        # Act
        result = provider.remove_group_member(
            "SG-ADMIN@EXAMPLE.COM",
            "USER@EXAMPLE.COM",
        )

        # Assert
        assert result.is_success
        assert result.data is None
        google_service.members.return_value.delete.assert_called_once_with(
            groupKey="sg-admin@example.com",
            memberKey="user@example.com",
        )

    def test_propagates_directory_error(self, provider, google_service):
        # Arrange
        google_service.members.return_value.delete.return_value.execute.side_effect = _http_error(503)

        # Act
        result = provider.remove_group_member("sg-admin@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR


class TestCheckMembership:
    def test_returns_true_when_user_is_member(self, provider, google_service):
        # Arrange
        google_service.members.return_value.hasMember.return_value = _request({"isMember": True})

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

    def test_returns_false_when_user_is_not_member(self, provider, google_service):
        # Arrange
        google_service.members.return_value.hasMember.return_value = _request({"isMember": False})

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

    def test_returns_false_when_not_a_member(self, provider, google_service):
        # Arrange
        google_service.members.return_value.hasMember.return_value = _request({"isMember": False})

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

    def test_normalises_group_key_and_email_to_lowercase(self, provider, google_service):
        # Arrange
        google_service.members.return_value.hasMember.return_value = _request({"isMember": False})

        # Act
        provider.check_membership("SG-TEAM@EXAMPLE.COM", "USER@EXAMPLE.COM")

        # Assert
        google_service.members.return_value.hasMember.assert_called_once_with(
            groupKey="sg-team@example.com",
            memberKey="user@example.com",
        )

    def test_propagates_directory_error(self, provider, google_service):
        # Arrange
        google_service.members.return_value.hasMember.return_value.execute.side_effect = _http_error(404)

        # Act
        result = provider.check_membership("sg-ghost@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.NOT_FOUND

    def test_returns_error_when_has_member_payload_is_not_dict(self, provider, google_service):
        # Arrange
        google_service.members.return_value.hasMember.return_value = _request(None)

        # Act
        result = provider.check_membership("sg-team@example.com", "user@example.com")

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_MEMBERSHIP_PAYLOAD_INVALID"


class TestListGroups:
    def test_returns_canonical_groups_for_query(self, provider, google_service):
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
        google_service.groups.return_value.list.return_value = _request({"groups": groups})

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
        google_service.groups.return_value.list.assert_called_once_with(customer="my_customer")

    def test_uses_group_alias_fields_when_standard_keys_are_missing(self, provider, google_service):
        # Arrange
        groups = [
            {
                "groupEmail": "SG-OPS@EXAMPLE.COM",
                "groupId": "group-9",
                "displayName": "Ops",
            }
        ]
        google_service.groups.return_value.list.return_value = _request({"groups": groups})

        # Act
        result = provider.list_groups(query="email:sg-*")

        # Assert
        assert result.is_success
        google_service.groups.return_value.list.assert_called_once_with(customer="my_customer")
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

    def test_prefers_managed_alias_when_primary_email_uses_old_pattern(self, provider, google_service):
        # Arrange
        google_service.groups.return_value.list.return_value = _request(
            {
                "groups": [
                    {
                        "email": "aws-finops@example.com",
                        "aliases": ["sg-aws-finops@example.com"],
                        "id": "group-10",
                        "name": "FinOps",
                    }
                ]
            }
        )

        # Act
        result = provider.list_groups(query="sg-aws-")

        # Assert
        assert result.is_success
        google_service.groups.return_value.list.assert_called_once_with(customer="my_customer")
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

    def test_skips_groups_when_email_is_missing_for_alias_aware_discovery(self, provider, google_service):
        # Arrange
        google_service.groups.return_value.list.return_value = _request({"groups": [{"id": "group-1", "name": "Admins"}]})

        # Act
        result = provider.list_groups(query="sg-")

        # Assert
        assert result.is_success
        assert result.data == []
        google_service.groups.return_value.list.assert_called_once_with(customer="my_customer")

    def test_returns_error_when_managed_group_domain_mismatches(self, provider, google_service):
        # Arrange
        google_service.groups.return_value.list.return_value = _request(
            {
                "groups": [
                    {
                        "email": "platform-admins@other.example",
                        "id": "group-1",
                        "name": "Admins",
                    }
                ]
            }
        )

        # Act
        result = provider.list_groups(query="name:Admins")

        # Assert
        # name:Admins is a Google query expression — passed through unchanged
        google_service.groups.return_value.list.assert_called_once_with(customer="my_customer", query="name:Admins")
        assert not result.is_success
        assert result.error_code == "DIRECTORY_GROUP_DOMAIN_MISMATCH"

    def test_propagates_directory_error(self, provider, google_service):
        # Arrange
        google_service.groups.return_value.list.return_value.execute.side_effect = _http_error(503)

        # Act
        result = provider.list_groups(query="sg-")

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR


class TestGetGroupMembersBatch:
    def test_returns_members_for_each_group(self, provider, google_service):
        # Arrange
        _install_fake_batch(
            google_service,
            {
                "sg-aws-admin@example.com": {
                    "members": [{"email": "alice@example.com", "type": "USER", "id": "m1"}],
                },
                "sg-aws-read@example.com": {
                    "members": [{"email": "bob@example.com", "type": "USER", "id": "m2"}],
                },
            },
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

    def test_returns_empty_dict_for_empty_input(self, provider, google_service):
        # Act
        result = provider.get_group_members_batch([])

        # Assert
        assert result.is_success
        assert result.data == {}
        google_service.new_batch_http_request.assert_not_called()

    def test_propagates_batch_failure(self, provider, google_service):
        # Arrange
        _install_fake_batch(google_service, {})

        # Act
        result = provider.get_group_members_batch(["sg-aws-admin@example.com"])

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR

    def test_filters_to_requested_member_types(self, provider, google_service):
        # Arrange
        _install_fake_batch(
            google_service,
            {
                "sg-aws-admin@example.com": {
                    "members": [
                        {"email": "alice@example.com", "type": "USER", "id": "m1"},
                        {
                            "email": "nested-group@example.com",
                            "type": "GROUP",
                            "id": "m2",
                        },
                    ],
                },
            },
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

    def test_normalises_group_keys_to_lowercase(self, provider, google_service):
        # Arrange
        _install_fake_batch(google_service, {"sg-aws-admin@example.com": {"members": []}})

        # Act
        provider.get_group_members_batch(["SG-AWS-Admin@EXAMPLE.COM"])

        # Assert
        google_service.members.return_value.list.assert_called_once_with(groupKey="sg-aws-admin@example.com")
