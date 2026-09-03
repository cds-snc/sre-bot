"""Unit tests for GoogleDirectoryProvider."""

from inspect import signature
from typing import Any
from unittest.mock import MagicMock

import httplib2
import pytest
from googleapiclient.errors import HttpError
from structlog.testing import capture_logs

from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
)
from infrastructure.directory.provider import DirectoryProvider
from infrastructure.operations.status import OperationStatus


def _request(payload: Any) -> MagicMock:
    """Build a fake googleapiclient request whose execute() returns payload."""
    request = MagicMock()
    request.execute.return_value = payload
    return request


def _http_error(status: int) -> HttpError:
    """Build a fake googleapiclient HttpError carrying the given HTTP status."""
    return HttpError(httplib2.Response({"status": status}), b"{}")


def _install_pages(resource: MagicMock, response_key: str, pages: list[list[Any]]) -> list[MagicMock]:
    """Wire resource.list/list_next to walk the given pages, returning each page request.

    Callers assert on which page requests were executed to prove pagination stops early.
    """
    requests = [_request({response_key: page}) for page in pages]
    resource.list.return_value = requests[0]

    def list_next(request: MagicMock, _response: Any) -> MagicMock | None:
        index = next(i for i, candidate in enumerate(requests) if candidate is request)
        return requests[index + 1] if index + 1 < len(requests) else None

    resource.list_next.side_effect = list_next
    return requests


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
            given_name="Alias",
            family_name="User",
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

    def test_returns_empty_list_when_limit_is_non_positive(self, provider, google_service):
        # Act
        result = provider.list_users(limit=0)

        # Assert
        assert result.is_success
        assert result.data == []
        google_service.users.return_value.list.assert_not_called()

    def test_limit_none_returns_every_user_across_pages(self, provider, google_service):
        # Arrange
        _install_pages(
            google_service.users.return_value,
            "users",
            [
                [{"primaryEmail": "user1@example.com", "id": "user-1"}],
                [{"primaryEmail": "user2@example.com", "id": "user-2"}],
                [{"primaryEmail": "user3@example.com", "id": "user-3"}],
            ],
        )

        # Act
        result = provider.list_users()

        # Assert
        assert result.is_success
        assert [user.email for user in result.data] == [
            "user1@example.com",
            "user2@example.com",
            "user3@example.com",
        ]

    def test_unbounded_listing_requests_the_admin_sdk_page_size(self, provider, google_service):
        # Arrange
        _install_pages(google_service.users.return_value, "users", [[]])

        # Act
        provider.list_users()

        # Assert
        google_service.users.return_value.list.assert_called_once_with(
            customer="my_customer",
            maxResults=500,
            query=None,
        )

    def test_limit_stops_before_fetching_the_next_page(self, provider, google_service):
        # Arrange
        _install_pages(
            google_service.users.return_value,
            "users",
            [
                [{"primaryEmail": f"user{index}@example.com", "id": f"user-{index}"} for index in range(5)],
                [{"primaryEmail": "user9@example.com", "id": "user-9"}],
            ],
        )

        # Act
        result = provider.list_users(limit=2)

        # Assert
        assert result.is_success
        assert [user.email for user in result.data] == [
            "user0@example.com",
            "user1@example.com",
        ]
        google_service.users.return_value.list_next.assert_not_called()

    def test_limit_spanning_a_page_boundary_stops_at_the_second_page(self, provider, google_service):
        # Arrange
        page_requests = _install_pages(
            google_service.users.return_value,
            "users",
            [
                [{"primaryEmail": "user1@example.com", "id": "user-1"}, {"primaryEmail": "user2@example.com", "id": "user-2"}],
                [{"primaryEmail": "user3@example.com", "id": "user-3"}, {"primaryEmail": "user4@example.com", "id": "user-4"}],
                [{"primaryEmail": "user5@example.com", "id": "user-5"}],
            ],
        )

        # Act
        result = provider.list_users(limit=3)

        # Assert
        assert result.is_success
        assert len(result.data) == 3
        assert page_requests[1].execute.called
        assert not page_requests[2].execute.called

    def test_limit_equal_to_available_entries_does_not_fetch_another_page(self, provider, google_service):
        # Arrange
        _install_pages(
            google_service.users.return_value,
            "users",
            [
                [{"primaryEmail": "user1@example.com", "id": "user-1"}, {"primaryEmail": "user2@example.com", "id": "user-2"}],
                [{"primaryEmail": "user3@example.com", "id": "user-3"}],
            ],
        )

        # Act
        result = provider.list_users(limit=2)

        # Assert
        assert result.is_success
        assert len(result.data) == 2
        google_service.users.return_value.list_next.assert_not_called()

    def test_user_carries_given_and_family_name(self, provider, google_service):
        # Arrange
        google_service.users.return_value.list.return_value = _request(
            {
                "users": [
                    {
                        "primaryEmail": "user1@example.com",
                        "id": "user-1",
                        "name": {
                            "givenName": "User",
                            "familyName": "One",
                            "fullName": "User One",
                        },
                    }
                ]
            }
        )

        # Act
        result = provider.list_users()

        # Assert
        assert result.is_success
        assert result.data == [
            DirectoryUser(
                email="user1@example.com",
                provider_user_id="user-1",
                display_name="User One",
                given_name="User",
                family_name="One",
                is_active=None,
                provider="google",
            )
        ]

    @pytest.mark.parametrize("name_payload", [{}, {"name": "User One"}])
    def test_name_fields_are_none_when_name_block_is_absent_or_a_string(self, provider, google_service, name_payload):
        # Arrange
        google_service.users.return_value.list.return_value = _request(
            {"users": [{"primaryEmail": "user1@example.com", "id": "user-1", **name_payload}]}
        )

        # Act
        result = provider.list_users()

        # Assert
        assert result.is_success
        assert result.data[0].given_name is None
        assert result.data[0].family_name is None

    def test_returns_empty_list_for_a_single_empty_page(self, provider, google_service):
        # Arrange
        _install_pages(google_service.users.return_value, "users", [[]])

        # Act
        result = provider.list_users()

        # Assert
        assert result.is_success
        assert result.data == []

    def test_returns_error_when_a_users_entry_is_not_a_dict(self, provider, google_service):
        # Arrange
        google_service.users.return_value.list.return_value = _request({"users": ["not-a-dict"]})

        # Act
        result = provider.list_users()

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_USERS_PAYLOAD_INVALID"

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

    def test_empty_query_returns_every_group_across_pages(self, provider, google_service):
        # Arrange
        _install_pages(
            google_service.groups.return_value,
            "groups",
            [
                [{"email": "sg-admin@example.com", "id": "group-1", "name": "Admins"}],
                [{"email": "sg-devs@example.com", "id": "group-2", "name": "Developers"}],
            ],
        )

        # Act
        result = provider.list_groups()

        # Assert
        assert result.is_success
        assert [group.group_email for group in result.data] == [
            "sg-admin@example.com",
            "sg-devs@example.com",
        ]
        google_service.groups.return_value.list.assert_called_once_with(customer="my_customer", maxResults=200)

    def test_empty_query_does_not_apply_the_managed_prefix_filter(self, provider, google_service):
        # Arrange
        _install_pages(
            google_service.groups.return_value,
            "groups",
            [
                [
                    {"email": "sg-admin@example.com", "id": "group-1"},
                    {"email": "marketing@example.com", "id": "group-2"},
                ]
            ],
        )

        # Act
        result = provider.list_groups(query="")

        # Assert
        assert result.is_success
        assert [group.group_email for group in result.data] == [
            "sg-admin@example.com",
            "marketing@example.com",
        ]

    def test_empty_query_accepts_a_group_outside_the_managed_domain(self, provider, google_service):
        # Arrange
        _install_pages(
            google_service.groups.return_value,
            "groups",
            [[{"email": "platform-admins@other.example", "id": "group-1", "name": "Admins"}]],
        )

        # Act
        result = provider.list_groups(query="")

        # Assert
        assert result.is_success
        assert result.data == [
            DirectoryGroup(
                group_email="platform-admins@other.example",
                group_slug="platform-admins",
                provider_group_id="group-1",
                name="Admins",
                description=None,
                provider="google",
            )
        ]

    def test_empty_query_ignores_managed_alias_preference(self, provider, google_service):
        # Arrange
        _install_pages(
            google_service.groups.return_value,
            "groups",
            [
                [
                    {
                        "email": "aws-finops@example.com",
                        "aliases": ["sg-aws-finops@example.com"],
                        "id": "group-10",
                    }
                ]
            ],
        )

        # Act
        result = provider.list_groups(query="")

        # Assert
        assert result.is_success
        assert result.data[0].group_email == "aws-finops@example.com"
        assert result.data[0].group_slug == "aws-finops"

    def test_returns_empty_list_when_groups_key_is_empty(self, provider, google_service):
        # Arrange
        _install_pages(google_service.groups.return_value, "groups", [[]])

        # Act
        result = provider.list_groups(query="")

        # Assert
        assert result.is_success
        assert result.data == []

    def test_unmappable_group_is_logged_and_counted(self, provider, google_service):
        # Arrange
        _install_pages(
            google_service.groups.return_value,
            "groups",
            [
                [
                    {"id": "group-broken", "name": "No Email"},
                    {"email": "sg-admin@example.com", "id": "group-1"},
                ]
            ],
        )

        # Act
        with capture_logs() as entries:
            result = provider.list_groups(query="")

        # Assert
        assert result.is_success
        assert [group.group_email for group in result.data] == ["sg-admin@example.com"]
        skipped = [entry for entry in entries if entry["event"] == "directory_group_skipped"]
        assert len(skipped) == 1
        assert skipped[0]["log_level"] == "warning"
        assert "group-broken" in str(skipped[0].values())
        completed = [entry for entry in entries if entry["event"] == "directory_groups_listed"]
        assert len(completed) == 1
        assert completed[0]["skipped"] == 1
        assert completed[0]["returned"] == 1

    def test_managed_path_skip_is_logged_and_counted(self, google_service, mock_directory_settings):
        # Arrange
        mock_directory_settings.enforce_managed_group_email = False
        provider = GoogleDirectoryProvider(
            get_service=lambda scopes: google_service,
            directory_settings=mock_directory_settings,
            customer_id="my_customer",
        )
        _install_pages(
            google_service.groups.return_value,
            "groups",
            [
                [
                    {"id": "group-broken", "name": "No Email"},
                    {"email": "sg-admin@example.com", "id": "group-1"},
                ]
            ],
        )

        # Act
        with capture_logs() as entries:
            result = provider.list_groups(query="sg-")

        # Assert
        assert result.is_success
        assert [group.group_email for group in result.data] == ["sg-admin@example.com"]
        assert any(entry["event"] == "directory_group_skipped" for entry in entries)
        completed = [entry for entry in entries if entry["event"] == "directory_groups_listed"]
        assert completed and completed[0]["skipped"] == 1


class TestDirectoryProviderProtocolSignatures:
    def test_list_users_defaults_to_the_whole_directory(self):
        # Assert
        assert signature(DirectoryProvider.list_users).parameters["limit"].default is None

    def test_list_groups_query_is_optional(self):
        # Assert
        assert signature(DirectoryProvider.list_groups).parameters["query"].default == ""


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
