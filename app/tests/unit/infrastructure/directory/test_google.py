"""Unit tests for GoogleDirectoryProvider."""

from inspect import signature
from typing import Any
from unittest.mock import MagicMock

import httplib2
import pytest
from googleapiclient.errors import HttpError
from structlog.testing import capture_logs

from infrastructure.directory import google as google_module
from infrastructure.directory import models as directory_models
from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
)
from infrastructure.directory.provider import DirectoryProvider
from infrastructure.operations.status import OperationStatus

# Contract values asserted by the batch tests; the provider owns the constants.
_MEMBERS_PAGE_SIZE = 200
_BATCH_MAX_REQUESTS = 100


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


def _install_paged_batch(
    service: MagicMock,
    pages_by_key: dict[str, list[list[dict[str, Any]]]],
    errors_by_key: dict[str, Exception] | None = None,
) -> list[list[str]]:
    """Wire members.list/list_next plus a batch double that pages per group key.

    ``pages_by_key`` maps a group key to its ordered member pages, so a key with
    more than one page proves the provider re-batches until the pages are
    exhausted. Returns the per-``new_batch_http_request``-call list of added
    request ids, which tests assert on to prove chunking and re-batching.
    """
    errors = errors_by_key or {}
    rounds: list[list[str]] = []
    members_resource = service.members.return_value

    requests_by_key: dict[str, list[MagicMock]] = {}
    payload_by_request: dict[int, dict[str, Any]] = {}
    position_by_request: dict[int, tuple[str, int]] = {}

    for key in {**pages_by_key, **dict.fromkeys(errors, [[]])}:
        pages = pages_by_key.get(key) or [[]]
        page_requests: list[MagicMock] = []
        for index, page in enumerate(pages):
            request = MagicMock(name=f"{key}-page-{index}")
            payload: dict[str, Any] = {"members": page}
            if index + 1 < len(pages):
                payload["nextPageToken"] = f"{key}-token-{index}"
            payload_by_request[id(request)] = payload
            position_by_request[id(request)] = (key, index)
            page_requests.append(request)
        requests_by_key[key] = page_requests

    members_resource.list.side_effect = lambda groupKey, **_kwargs: requests_by_key[groupKey][0]

    def list_next(previous_request: MagicMock, _previous_response: Any) -> MagicMock | None:
        key, index = position_by_request[id(previous_request)]
        page_requests = requests_by_key[key]
        return page_requests[index + 1] if index + 1 < len(page_requests) else None

    members_resource.list_next.side_effect = list_next

    def new_batch_http_request(callback):
        added: list[tuple[str, MagicMock]] = []
        round_ids: list[str] = []
        rounds.append(round_ids)
        batch = MagicMock()

        def add(request, request_id):
            added.append((request_id, request))
            round_ids.append(request_id)

        def execute(**_kwargs):
            for request_id, request in added:
                error = errors.get(request_id)
                if error is not None:
                    callback(request_id, None, error)
                else:
                    callback(request_id, payload_by_request[id(request)], None)

        batch.add.side_effect = add
        batch.execute.side_effect = execute
        return batch

    service.new_batch_http_request.side_effect = new_batch_http_request
    return rounds


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

    def test_name_parts_are_none_when_name_is_string_or_absent(self, provider, google_service):
        """Verify given_name and family_name remain None when name is a bare string or missing."""
        # Arrange
        google_service.users.return_value.get.return_value = _request(
            {
                "primaryEmail": "user@example.com",
                "id": "user-789",
                "name": "Bare Name String",
            }
        )

        # Act
        result = provider.get_user("user@example.com")

        # Assert
        assert result.is_success
        assert result.data.given_name is None
        assert result.data.family_name is None
        assert result.data.display_name == "Bare Name String"

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
        google_service.groups.return_value.list.assert_called_once_with(customer="my_customer", maxResults=200)

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
        google_service.groups.return_value.list.assert_called_once_with(customer="my_customer", maxResults=200)
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
        google_service.groups.return_value.list.assert_called_once_with(customer="my_customer", maxResults=200)
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
        google_service.groups.return_value.list.assert_called_once_with(customer="my_customer", maxResults=200)

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
        google_service.groups.return_value.list.assert_called_once_with(
            customer="my_customer", maxResults=200, query="name:Admins"
        )
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
        _install_paged_batch(
            google_service,
            {
                "sg-aws-admin@example.com": [[{"email": "alice@example.com", "type": "USER", "id": "m1"}]],
                "sg-aws-read@example.com": [[{"email": "bob@example.com", "type": "USER", "id": "m2"}]],
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

    def test_filters_to_requested_member_types(self, provider, google_service):
        # Arrange
        _install_paged_batch(
            google_service,
            {
                "sg-aws-admin@example.com": [
                    [
                        {"email": "alice@example.com", "type": "USER", "id": "m1"},
                        {"email": "nested-group@example.com", "type": "GROUP", "id": "m2"},
                    ]
                ],
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

    def test_empty_member_types_returns_error_without_issuing_a_request(self, provider, google_service):
        # Arrange
        _install_paged_batch(google_service, {"sg-aws-admin@example.com": [[]]})

        # Act
        result = provider.get_group_members_batch(["sg-aws-admin@example.com"], include_member_types=set())

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_MEMBER_TYPES_INVALID"
        google_service.new_batch_http_request.assert_not_called()

    def test_normalises_group_keys_to_lowercase(self, provider, google_service):
        # Arrange
        _install_paged_batch(google_service, {"sg-aws-admin@example.com": [[]]})

        # Act
        provider.get_group_members_batch(["SG-AWS-Admin@EXAMPLE.COM"])

        # Assert
        google_service.members.return_value.list.assert_called_once_with(
            groupKey="sg-aws-admin@example.com",
            maxResults=_MEMBERS_PAGE_SIZE,
        )

    def test_batched_list_requests_use_the_members_page_size(self, provider, google_service):
        # Arrange
        _install_paged_batch(
            google_service,
            {"sg-a@example.com": [[]], "sg-b@example.com": [[]]},
        )

        # Act
        provider.get_group_members_batch(["sg-a@example.com", "sg-b@example.com"])

        # Assert
        page_sizes = {call.kwargs["maxResults"] for call in google_service.members.return_value.list.call_args_list}
        assert page_sizes == {_MEMBERS_PAGE_SIZE}

    def test_vendor_batch_helper_is_not_imported(self):
        # Assert
        assert not hasattr(google_module, "execute_batch_request")

    def test_surfaces_per_key_response_and_error(self, provider, google_service):
        # Arrange
        _install_paged_batch(
            google_service,
            {"sg-a@example.com": [[{"email": "alice@example.com", "type": "USER", "id": "m1"}]]},
            errors_by_key={"sg-b@example.com": _http_error(429)},
        )
        members_resource = google_service.members()
        requests = {
            key: members_resource.list(groupKey=key, maxResults=_MEMBERS_PAGE_SIZE)
            for key in ("sg-a@example.com", "sg-b@example.com")
        }

        # Act
        responses, errors = provider._execute_batch_round(google_service, requests)

        # Assert
        assert responses["sg-a@example.com"]["members"][0]["email"] == "alice@example.com"
        assert "sg-b@example.com" not in responses
        assert isinstance(errors["sg-b@example.com"], HttpError)
        assert "sg-a@example.com" not in errors

    def test_paginates_members_across_batch_rounds(self, provider, google_service):
        # Arrange
        _install_paged_batch(
            google_service,
            {
                "sg-aws-admin@example.com": [
                    [{"email": "alice@example.com", "type": "USER", "id": "m1"}],
                    [{"email": "bob@example.com", "type": "USER", "id": "m2"}],
                ]
            },
        )

        # Act
        result = provider.get_group_members_batch(["sg-aws-admin@example.com"])

        # Assert
        assert result.is_success
        assert [member.email for member in result.data["sg-aws-admin@example.com"]] == [
            "alice@example.com",
            "bob@example.com",
        ]

    def test_second_round_rebatches_only_unfinished_groups(self, provider, google_service):
        # Arrange
        rounds = _install_paged_batch(
            google_service,
            {
                "sg-paged@example.com": [
                    [{"email": "alice@example.com", "type": "USER", "id": "m1"}],
                    [{"email": "bob@example.com", "type": "USER", "id": "m2"}],
                ],
                "sg-done@example.com": [[{"email": "carol@example.com", "type": "USER", "id": "m3"}]],
            },
        )

        # Act
        result = provider.get_group_members_batch(["sg-paged@example.com", "sg-done@example.com"])

        # Assert
        assert result.is_success
        assert len(rounds) == 2
        assert set(rounds[0]) == {"sg-paged@example.com", "sg-done@example.com"}
        assert rounds[1] == ["sg-paged@example.com"]

    def test_chunks_batch_rounds_at_the_request_limit(self, provider, google_service):
        # Arrange
        group_keys = [f"sg-{index}@example.com" for index in range(150)]
        rounds = _install_paged_batch(
            google_service,
            {key: [[{"email": f"user-{key}", "type": "USER", "id": key}]] for key in group_keys},
        )

        # Act
        result = provider.get_group_members_batch(group_keys)

        # Assert
        assert result.is_success
        assert len(rounds) == 2
        assert [len(round_ids) for round_ids in rounds] == [_BATCH_MAX_REQUESTS, 50]
        assert set(result.data.keys()) == set(group_keys)

    def test_one_failing_group_fails_the_whole_batch_with_a_classified_status(self, provider, google_service):
        # Arrange
        _install_paged_batch(
            google_service,
            {"sg-ok@example.com": [[{"email": "alice@example.com", "type": "USER", "id": "m1"}]]},
            errors_by_key={"sg-bad@example.com": _http_error(429)},
        )

        # Act
        result = provider.get_group_members_batch(["sg-ok@example.com", "sg-bad@example.com"])

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "429"

    def test_signature_is_unchanged(self):
        # Assert
        parameters = signature(GoogleDirectoryProvider.get_group_members_batch).parameters
        assert list(parameters) == ["self", "group_keys", "include_member_types"]
        assert parameters["include_member_types"].default is None


class TestListGroupsWithMembers:
    @staticmethod
    def _install_groups(google_service, emails: list[str]) -> None:
        """Wire groups.list to return one canonical group per email."""
        google_service.groups.return_value.list.return_value = _request(
            {"groups": [{"email": email, "id": f"group-{index}", "name": email} for index, email in enumerate(emails)]}
        )

    def test_protocol_declares_the_composition(self):
        # Assert
        parameters = signature(DirectoryProvider.list_groups_with_members).parameters
        assert list(parameters) == ["self", "query", "limit", "include_member_types"]
        assert parameters["query"].default == ""
        assert parameters["limit"].default is None
        assert parameters["include_member_types"].default is None

    def test_returns_typed_groups_with_members(self, provider, google_service):
        # Arrange
        self._install_groups(google_service, ["sg-a@example.com", "sg-b@example.com"])
        _install_paged_batch(
            google_service,
            {
                "sg-a@example.com": [[{"email": "alice@example.com", "type": "USER", "id": "m1"}]],
                "sg-b@example.com": [[{"email": "bob@example.com", "type": "USER", "id": "m2"}]],
            },
        )

        # Act
        result = provider.list_groups_with_members()

        # Assert
        assert result.is_success
        payload = result.data
        assert isinstance(payload, directory_models.DirectoryGroupsWithMembers)
        assert payload.failures == ()
        assert isinstance(payload.groups, tuple)
        by_email = {entry.group.group_email: entry for entry in payload.groups}
        assert set(by_email) == {"sg-a@example.com", "sg-b@example.com"}
        entry = by_email["sg-a@example.com"]
        assert isinstance(entry, directory_models.DirectoryGroupWithMembers)
        assert isinstance(entry.group, DirectoryGroup)
        assert entry.members == (
            DirectoryMember(
                email="alice@example.com",
                membership_id="m1",
                provider_user_id="m1",
                member_type="USER",
                role=None,
                provider="google",
            ),
        )

    def test_issues_one_batched_round_trip_per_page_depth(self, provider, google_service):
        # Arrange
        self._install_groups(google_service, ["sg-a@example.com", "sg-b@example.com"])
        rounds = _install_paged_batch(
            google_service,
            {"sg-a@example.com": [[]], "sg-b@example.com": [[]]},
        )

        # Act
        result = provider.list_groups_with_members()

        # Assert
        assert result.is_success
        assert len(rounds) == 1
        assert set(rounds[0]) == {"sg-a@example.com", "sg-b@example.com"}

    def test_group_requiring_a_second_page_returns_every_member_in_order(self, provider, google_service):
        # Arrange
        self._install_groups(google_service, ["sg-a@example.com"])
        _install_paged_batch(
            google_service,
            {
                "sg-a@example.com": [
                    [{"email": "alice@example.com", "type": "USER", "id": "m1"}],
                    [{"email": "bob@example.com", "type": "USER", "id": "m2"}],
                ]
            },
        )

        # Act
        result = provider.list_groups_with_members()

        # Assert
        assert result.is_success
        assert [member.email for member in result.data.groups[0].members] == [
            "alice@example.com",
            "bob@example.com",
        ]

    def test_failed_group_is_carried_in_failures_with_classified_status(self, provider, google_service):
        # Arrange
        self._install_groups(google_service, ["sg-ok@example.com", "sg-bad@example.com"])
        _install_paged_batch(
            google_service,
            {"sg-ok@example.com": [[{"email": "alice@example.com", "type": "USER", "id": "m1"}]]},
            errors_by_key={"sg-bad@example.com": _http_error(429)},
        )

        # Act
        result = provider.list_groups_with_members()

        # Assert
        assert result.is_success
        payload = result.data
        assert [entry.group.group_email for entry in payload.groups] == ["sg-ok@example.com"]
        assert len(payload.failures) == 1
        failure = payload.failures[0]
        assert isinstance(failure, directory_models.DirectoryGroupFailure)
        assert failure.group_email == "sg-bad@example.com"
        assert failure.status == OperationStatus.TRANSIENT_ERROR
        assert failure.error_code == "429"
        assert failure.message

    def test_unmapped_per_group_http_error_propagates(self, provider, google_service):
        # Arrange
        self._install_groups(google_service, ["sg-bad@example.com"])
        _install_paged_batch(
            google_service,
            {},
            errors_by_key={"sg-bad@example.com": _http_error(400)},
        )

        # Act / Assert
        with pytest.raises(HttpError):
            provider.list_groups_with_members()

    def test_empty_group_list_returns_empty_payload_without_batching(self, provider, google_service):
        # Arrange
        self._install_groups(google_service, [])
        _install_paged_batch(google_service, {})

        # Act
        result = provider.list_groups_with_members()

        # Assert
        assert result.is_success
        assert result.data.groups == ()
        assert result.data.failures == ()
        google_service.new_batch_http_request.assert_not_called()

    def test_group_set_spanning_more_than_one_chunk_is_merged(self, provider, google_service):
        # Arrange
        emails = [f"sg-{index}@example.com" for index in range(150)]
        self._install_groups(google_service, emails)
        rounds = _install_paged_batch(
            google_service,
            {email: [[{"email": f"user-{email}", "type": "USER", "id": email}]] for email in emails},
        )

        # Act
        result = provider.list_groups_with_members()

        # Assert
        assert result.is_success
        assert len(rounds) == 2
        assert [len(round_ids) for round_ids in rounds] == [_BATCH_MAX_REQUESTS, 50]
        assert {entry.group.group_email for entry in result.data.groups} == set(emails)

    def test_zero_member_group_is_included(self, provider, google_service):
        # Arrange
        self._install_groups(google_service, ["sg-empty@example.com"])
        _install_paged_batch(google_service, {"sg-empty@example.com": [[]]})

        # Act
        result = provider.list_groups_with_members()

        # Assert
        assert result.is_success
        assert len(result.data.groups) == 1
        assert result.data.groups[0].group.group_email == "sg-empty@example.com"
        assert result.data.groups[0].members == ()

    def test_members_are_not_merged_with_user_records(self, provider, google_service):
        # Arrange
        self._install_groups(google_service, ["sg-a@example.com"])
        _install_paged_batch(
            google_service,
            {"sg-a@example.com": [[{"email": "alice@example.com", "type": "USER", "id": "m1"}]]},
        )

        # Act
        result = provider.list_groups_with_members()

        # Assert
        assert result.is_success
        assert all(isinstance(member, DirectoryMember) for member in result.data.groups[0].members)
        google_service.users.assert_not_called()

    def test_propagates_list_groups_error_without_batching(self, provider, google_service):
        # Arrange
        google_service.groups.return_value.list.return_value.execute.side_effect = _http_error(503)
        _install_paged_batch(google_service, {})

        # Act
        result = provider.list_groups_with_members()

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.TRANSIENT_ERROR
        google_service.new_batch_http_request.assert_not_called()

    def test_empty_member_types_returns_error_without_batching(self, provider, google_service):
        # Arrange
        self._install_groups(google_service, ["sg-a@example.com"])
        _install_paged_batch(google_service, {"sg-a@example.com": [[]]})

        # Act
        result = provider.list_groups_with_members(include_member_types=set())

        # Assert
        assert not result.is_success
        assert result.error_code == "DIRECTORY_MEMBER_TYPES_INVALID"
        google_service.new_batch_http_request.assert_not_called()
