"""
Provider-level conftest.py for integration tests.

Provides provider-specific mocks and fixtures:
- Google Directory API mock
- AWS Identity Store API mock
- Provider instance fixtures
- Provider response fixtures

These fixtures allow testing provider integration without making
real API calls while simulating realistic API responses.
"""

import pytest
from unittest.mock import MagicMock


# ============================================================================
# Google Directory API Mocks
# ============================================================================


@pytest.fixture
def mock_google_directory_service():
    """Mock Google Directory API service.

    Returns:
        MagicMock: Mocked Google Directory service
    """
    service = MagicMock()

    # Mock groups().list() response
    groups_list_response = {
        "groups": [
            {
                "id": "google-group-1",
                "email": "team-a@example.com",
                "name": "Team A",
                "description": "Integration test group",
            },
            {
                "id": "google-group-2",
                "email": "team-b@example.com",
                "name": "Team B",
                "description": "Another test group",
            },
        ]
    }

    service.groups().list().execute.return_value = groups_list_response

    # Mock members().list() response
    members_list_response = {
        "members": [
            {
                "id": "member-1",
                "email": "user1@example.com",
                "type": "USER",
                "status": "ACTIVE",
            },
            {
                "id": "member-2",
                "email": "user2@example.com",
                "type": "USER",
                "status": "ACTIVE",
            },
        ]
    }

    service.members().list().execute.return_value = members_list_response

    # Mock members().insert() for adding members
    insert_response = {
        "id": "new-member",
        "email": "newuser@example.com",
        "type": "USER",
        "status": "ACTIVE",
    }

    service.members().insert().execute.return_value = insert_response

    # Mock members().delete() for removing members
    service.members().delete().execute.return_value = {}

    # Mock members().update() for member updates
    update_response = {
        "id": "member-1",
        "email": "user1@example.com",
        "type": "USER",
        "status": "ACTIVE",
        "role": "MEMBER",
    }

    service.members().update().execute.return_value = update_response

    return service


@pytest.fixture
def mock_google_admin_service():
    """Mock Google Admin service for directory operations.

    Returns:
        MagicMock: Mocked Google Admin service
    """
    service = MagicMock()

    # Mock groups().create()
    create_response = {
        "id": "new-group-123",
        "email": "newgroup@example.com",
        "name": "New Group",
    }

    service.groups().create().execute.return_value = create_response

    # Mock groups().update()
    update_response = {
        "id": "group-123",
        "email": "group@example.com",
        "name": "Updated Group",
    }

    service.groups().update().execute.return_value = update_response

    # Mock groups().delete()
    service.groups().delete().execute.return_value = {}

    return service


@pytest.fixture
def google_provider_with_mocked_client(monkeypatch, mock_google_directory_service):
    """Google provider instance with mocked API client.

    Returns:
        GoogleWorkspaceProvider: Provider with mocked client
    """
    from modules.groups.providers.google_workspace import GoogleWorkspaceProvider

    provider = GoogleWorkspaceProvider()

    # Replace the client with our mock
    monkeypatch.setattr(provider, "client", mock_google_directory_service)

    return provider


@pytest.fixture
def mock_google_api_errors():
    """Mock Google API error responses.

    Returns:
        Dict: Various Google API error responses
    """
    return {
        "not_found": {"error": {"errors": [{"message": "Not found"}]}},
        "permission_denied": {"error": {"errors": [{"message": "Permission denied"}]}},
        "invalid_request": {"error": {"errors": [{"message": "Invalid request"}]}},
        "rate_limit": {"error": {"errors": [{"message": "Rate limit exceeded"}]}},
    }


# ============================================================================
# AWS Identity Store Mocks
# ============================================================================


@pytest.fixture
def mock_identity_store_next():
    """Mock integrations.aws.identity_store_next module.

    Provides mocked responses for AWS Identity Store API calls.
    Responses follow OperationResult with status/data structure.
    """
    from infrastructure.operations.result import OperationResult

    mock = MagicMock()

    # get_group_by_name: resolves display name to UUID GroupId
    def get_group_by_name(display_name):
        """Mock get_group_by_name - resolve display name to GroupId."""
        # Map common test group names to UUIDs
        group_map = {
            "group-456": "12345678-1234-5678-1234-567890abcdef",
            "empty-group": "87654321-4321-8765-4321-fedcba098765",
            "test-group": "aaaabbbb-cccc-dddd-eeee-ffffgggghhhh",
        }
        group_id = group_map.get(display_name)
        if group_id:
            return OperationResult.success(
                data={"GroupId": group_id, "DisplayName": display_name}
            )
        return OperationResult.permanent_error(
            message=f"Group not found: {display_name}", error_code="NOT_FOUND"
        )

    # get_user_by_username: resolve email to UserId
    def get_user_by_username(email):
        """Mock get_user_by_username - resolve email to UserId."""
        user_map = {
            "alice@example.com": "user-111",
            "bob@example.com": "user-222",
            "charlie@example.com": "user-333",
        }
        user_id = user_map.get(email)
        if user_id:
            return OperationResult.success(data={"UserId": user_id, "UserName": email})
        return OperationResult.permanent_error(
            message=f"User not found: {email}", error_code="NOT_FOUND"
        )

    # get_user: fetch full user details
    def get_user(user_id):
        """Mock get_user - fetch full user details."""
        user_map = {
            "user-111": {
                "UserId": "user-111",
                "UserName": "alice@example.com",
                "Emails": [{"Value": "alice@example.com"}],
                "Name": {"GivenName": "Alice", "FamilyName": "Smith"},
            },
            "user-222": {
                "UserId": "user-222",
                "UserName": "bob@example.com",
                "Emails": [{"Value": "bob@example.com"}],
                "Name": {"GivenName": "Bob", "FamilyName": "Jones"},
            },
            "user-333": {
                "UserId": "user-333",
                "UserName": "charlie@example.com",
                "Emails": [{"Value": "charlie@example.com"}],
                "Name": {"GivenName": "Charlie", "FamilyName": "Brown"},
            },
        }
        user_data = user_map.get(user_id)
        if user_data:
            return OperationResult.success(data=user_data)
        return OperationResult.permanent_error(
            message=f"User not found: {user_id}", error_code="NOT_FOUND"
        )

    # create_group_membership: add user to group
    def create_group_membership(group_id, user_id):
        """Mock create_group_membership."""
        return OperationResult.success(
            data={"MembershipId": f"membership-{group_id[:8]}-{user_id}"}
        )

    # delete_group_membership: remove user from group
    def delete_group_membership(membership_id):
        """Mock delete_group_membership."""
        return OperationResult.success(data=None)

    # get_group_membership_id: lookup membership for user in group
    def get_group_membership_id(group_id, user_id):
        """Mock get_group_membership_id."""
        return OperationResult.success(
            data={"MembershipId": f"membership-{group_id[:8]}-{user_id}"}
        )

    # list_group_memberships: list members of a group
    def list_group_memberships(group_id):
        """Mock list_group_memberships."""
        memberships = [
            {
                "MembershipId": f"membership-{group_id[:8]}-user-111",
                "GroupId": group_id,
                "MemberId": {"UserId": "user-111"},
            },
        ]
        return OperationResult.success(data=memberships)

    mock.get_group_by_name = get_group_by_name
    mock.get_user_by_username = get_user_by_username
    mock.get_user = get_user
    mock.create_group_membership = create_group_membership
    mock.delete_group_membership = delete_group_membership
    mock.get_group_membership_id = get_group_membership_id
    mock.list_group_memberships = list_group_memberships

    return mock


@pytest.fixture
def mock_aws_identity_store_client():
    """Mock AWS Identity Store API client.

    Returns:
        MagicMock: Mocked AWS Identity Store client
    """
    client = MagicMock()

    # Mock list_groups response
    list_groups_response = {
        "Groups": [
            {
                "GroupId": "aws-group-1",
                "DisplayName": "team-a",
                "Description": "Integration test group",
            },
            {
                "GroupId": "aws-group-2",
                "DisplayName": "team-b",
                "Description": "Another test group",
            },
        ]
    }

    client.list_groups.return_value = list_groups_response

    # Mock list_group_memberships response
    list_members_response = {
        "GroupMemberships": [
            {
                "MemberId": "member-1",
                "GroupId": "aws-group-1",
                "MembershipType": "GROUP",
            },
            {
                "MemberId": "member-2",
                "GroupId": "aws-group-1",
                "MembershipType": "USER",
            },
        ]
    }

    client.list_group_memberships.return_value = list_members_response

    # Mock create_group_membership response
    create_member_response = {
        "MemberId": "new-member",
        "GroupId": "aws-group-1",
        "MembershipType": "USER",
    }

    client.create_group_membership.return_value = create_member_response

    # Mock delete_group_membership
    client.delete_group_membership.return_value = {}

    # Mock get_user_id response (for email lookup)
    get_user_response = {
        "UserId": "aws-user-123",
        "UserName": "testuser",
        "DisplayName": "Test User",
    }

    client.get_user_id.return_value = get_user_response

    return client


@pytest.fixture
def mock_aws_iam_client():
    """Mock AWS IAM API client.

    Returns:
        MagicMock: Mocked AWS IAM client
    """
    client = MagicMock()

    # Mock get_group response
    get_group_response = {
        "Group": {
            "Path": "/divisions/",
            "GroupName": "test-group",
            "GroupId": "AIDAI23HXD2O5EXAMPLE",
            "Arn": "arn:aws:iam::123456789012:group/divisions/test-group",
            "CreateDate": "2025-01-01T00:00:00Z",
        },
        "Users": [
            {
                "Path": "/",
                "UserName": "testuser",
                "UserId": "AIDAI23HXD2O5USER",
                "Arn": "arn:aws:iam::123456789012:user/testuser",
                "CreateDate": "2025-01-01T00:00:00Z",
            }
        ],
    }

    client.get_group.return_value = get_group_response

    # Mock list_group_members response
    list_members_response = {
        "Users": [
            {
                "Path": "/",
                "UserName": "user1",
                "UserId": "AIDAI1",
                "Arn": "arn:aws:iam::123456789012:user/user1",
                "CreateDate": "2025-01-01T00:00:00Z",
            },
            {
                "Path": "/",
                "UserName": "user2",
                "UserId": "AIDAI2",
                "Arn": "arn:aws:iam::123456789012:user/user2",
                "CreateDate": "2025-01-01T00:00:00Z",
            },
        ],
        "IsTruncated": False,
    }

    client.get_group.return_value = list_members_response

    # Mock add_user_to_group
    client.add_user_to_group.return_value = {}

    # Mock remove_user_from_group
    client.remove_user_from_group.return_value = {}

    return client


@pytest.fixture
def aws_provider_with_mocked_clients(monkeypatch, mock_aws_identity_store_client):
    """AWS provider instance with mocked API clients.

    Returns:
        AwsProvider: Provider with mocked clients
    """
    from modules.groups.providers.aws_identity_center import AwsIdentityCenterProvider

    provider = AwsIdentityCenterProvider()

    # Replace the client with our mock
    monkeypatch.setattr(provider, "client", mock_aws_identity_store_client)

    return provider


@pytest.fixture
def mock_aws_api_errors():
    """Mock AWS API error responses.

    Returns:
        Dict: Various AWS API error responses
    """
    return {
        "group_not_found": {
            "Error": {
                "Code": "NoSuchEntity",
                "Message": "The group with name test-group cannot be found.",
            }
        },
        "user_not_found": {
            "Error": {
                "Code": "NoSuchEntity",
                "Message": "The user with name testuser cannot be found.",
            }
        },
        "user_already_in_group": {
            "Error": {
                "Code": "EntityAlreadyExists",
                "Message": "The user testuser is already a member of group test-group.",
            }
        },
        "service_unavailable": {
            "Error": {
                "Code": "ServiceUnavailable",
                "Message": "Service is temporarily unavailable.",
            }
        },
    }


# ============================================================================
# Provider Response Fixtures
# ============================================================================


@pytest.fixture
def google_group_api_response():
    """Realistic Google Group API response.

    Returns:
        Dict: Google Group data
    """
    return {
        "kind": "admin#directory#group",
        "etag": "test-etag-123",
        "id": "google-group-123",
        "email": "test-group@example.com",
        "name": "Test Group",
        "description": "Integration test group",
        "adminCreated": True,
        "directMembersCount": "5",
        "aliases": ["tg@example.com", "testgroup@example.com"],
    }


@pytest.fixture
def google_member_api_response():
    """Realistic Google Directory member API response.

    Returns:
        Dict: Google member data
    """
    return {
        "kind": "admin#directory#member",
        "etag": "test-etag-456",
        "id": "member-123",
        "email": "testuser@example.com",
        "type": "USER",
        "status": "ACTIVE",
        "role": "MEMBER",
    }


@pytest.fixture
def aws_group_api_response():
    """Realistic AWS group API response.

    Returns:
        Dict: AWS group data
    """
    return {
        "GroupId": "aws-group-456",
        "DisplayName": "test-group",
        "Description": "Integration test group",
        "CreateDate": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def aws_user_api_response():
    """Realistic AWS user API response.

    Returns:
        Dict: AWS user data
    """
    return {
        "UserId": "aws-user-789",
        "UserName": "testuser",
        "DisplayName": "Test User",
        "UserType": "PERSON",
        "CreateDate": "2025-01-01T00:00:00Z",
    }


# ============================================================================
# Test Markers
# ============================================================================


def pytest_configure(config):
    """Register provider-specific markers."""
    config.addinivalue_line(
        "markers",
        "integration_google: mark test as Google provider integration test",
    )
    config.addinivalue_line(
        "markers",
        "integration_aws: mark test as AWS provider integration test",
    )
