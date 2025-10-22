"""
Unit and integration tests for google_directory_next module.
"""

from unittest.mock import Mock, patch
from integrations.google_workspace import google_directory_next as gdn
from models.integrations import (
    IntegrationResponse,
    build_success_response,
    build_error_response,
)


class TestGetUser:
    """Test cases for get_user function."""

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_get_user_success(self, mock_execute):
        """Test successful user retrieval."""
        expected_user = {
            "id": "123456789",
            "primaryEmail": "test@example.com",
            "name": {"givenName": "Test", "familyName": "User"},
        }
        mock_execute.return_value = build_success_response(
            expected_user, "get_user", "google"
        )

        result = gdn.get_user("test@example.com")

        assert isinstance(result, IntegrationResponse)
        assert result.success is True
        assert result.data == expected_user
        assert result.function_name == "get_user"
        assert result.integration_name == "google"

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_get_user_not_found(self, mock_execute):
        """Test user not found scenario."""
        error = Exception("User not found")
        mock_execute.return_value = build_error_response(error, "get_user", "google")

        result = gdn.get_user("doesnotexist@example.com")

        assert isinstance(result, IntegrationResponse)
        assert result.success is False
        assert result.error["message"] == "User not found"
        assert result.function_name == "get_user"
        assert result.integration_name == "google"
        mock_execute.return_value = None

        result = gdn.get_user("nonexistent@example.com")

        assert result is None


class TestGetBatchUsers:
    """Test cases for get_batch_users function."""

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_users_success(
        self, mock_get_service, mock_batch_request, google_user_factory
    ):
        """Test successful batch user retrieval."""
        user_keys = ["user1@example.com", "user2@example.com"]
        users = google_user_factory(2, domain="example.com")

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        batch_data = {
            "results": {"user1@example.com": users[0], "user2@example.com": users[1]}
        }
        mock_batch_request.return_value = build_success_response(
            batch_data, "get_batch_users", "google"
        )

        result = gdn.get_batch_users(user_keys)

        assert isinstance(result, IntegrationResponse)
        assert result.success is True
        assert result.data == {
            "user1@example.com": users[0],
            "user2@example.com": users[1],
        }
        assert result.function_name == "get_batch_users"
        assert result.integration_name == "google"
        mock_get_service.assert_called_once()
        mock_batch_request.assert_called_once()

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_users_empty_list(self, mock_get_service, mock_batch_request):
        """Test batch user retrieval with empty list."""
        user_keys = []

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        batch_data = {"results": {}}
        mock_batch_request.return_value = build_success_response(
            batch_data, "get_batch_users", "google"
        )

        result = gdn.get_batch_users(user_keys)

        assert isinstance(result, IntegrationResponse)
        assert result.success is True
        assert result.data == {}
        assert result.function_name == "get_batch_users"
        assert result.integration_name == "google"


class TestListUsers:
    """Test cases for list_users function."""

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_list_users_success(self, mock_execute, google_user_factory):
        """Test successful user listing."""
        expected_users = google_user_factory(3)
        mock_execute.return_value = expected_users

        result = gdn.list_users()

        assert result == expected_users
        mock_execute.assert_called_once_with(
            "admin",
            "directory_v1",
            "users",
            "list",
            scopes=["https://www.googleapis.com/auth/admin.directory.user.readonly"],
            customer=gdn.GOOGLE_WORKSPACE_CUSTOMER_ID,
        )

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_list_users_with_kwargs(self, mock_execute):
        """Test user listing with additional kwargs."""
        mock_execute.return_value = []

        gdn.list_users(query="name:test*", maxResults=10)

        mock_execute.assert_called_once_with(
            "admin",
            "directory_v1",
            "users",
            "list",
            scopes=["https://www.googleapis.com/auth/admin.directory.user.readonly"],
            customer=gdn.GOOGLE_WORKSPACE_CUSTOMER_ID,
            query="name:test*",
            maxResults=10,
        )


class TestGetGroup:
    """Test cases for get_group function."""

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_get_group_success(self, mock_execute, google_group_factory):
        """Test successful group retrieval."""
        expected_group = google_group_factory(1)[0]
        mock_execute.return_value = expected_group

        result = gdn.get_group("test-group@example.com")

        assert result == expected_group
        mock_execute.assert_called_once_with(
            "admin",
            "directory_v1",
            "groups",
            "get",
            scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
            non_critical=True,
            groupKey="test-group@example.com",
        )


class TestGetBatchGroups:
    """Test cases for get_batch_groups function."""

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_groups_success(
        self, mock_get_service, mock_batch_request, google_group_factory
    ):
        """Test successful batch group retrieval."""
        group_keys = ["group1@example.com", "group2@example.com"]
        groups = google_group_factory(2, domain="example.com")

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_batch_request.return_value = {
            "results": {
                "group1@example.com": groups[0],
                "group2@example.com": groups[1],
            }
        }

        result = gdn.get_batch_groups(group_keys)

        assert len(result) == 2
        assert result["group1@example.com"] == groups[0]
        assert result["group2@example.com"] == groups[1]


class TestListGroups:
    """Test cases for list_groups function."""

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_list_groups_success(self, mock_execute, google_group_factory):
        """Test successful group listing."""
        expected_groups = google_group_factory(3)
        mock_execute.return_value = expected_groups

        result = gdn.list_groups()

        assert result == expected_groups
        mock_execute.assert_called_once_with(
            "admin",
            "directory_v1",
            "groups",
            "list",
            scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
            customer=gdn.GOOGLE_WORKSPACE_CUSTOMER_ID,
        )


class TestGetBatchMembers:
    """Test cases for get_batch_members function."""

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_members_success(
        self, mock_get_service, mock_batch_request, google_member_factory
    ):
        """Test successful batch member retrieval."""
        group_keys = ["group1@example.com", "group2@example.com"]
        members1 = google_member_factory(2, prefix="user1-", domain="example.com")
        members2 = google_member_factory(2, prefix="user2-", domain="example.com")

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_batch_request.return_value = {
            "results": {
                "group1@example.com": {"members": members1},
                "group2@example.com": {"members": members2},
            }
        }

        result = gdn.get_batch_members(group_keys)

        assert len(result) == 2
        assert result["group1@example.com"] == members1
        assert result["group2@example.com"] == members2

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_members_no_members(self, mock_get_service, mock_batch_request):
        """Test batch member retrieval when groups have no members."""
        group_keys = ["empty-group@example.com"]

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_batch_request.return_value = {"results": {"empty-group@example.com": None}}

        result = gdn.get_batch_members(group_keys)

        assert result["empty-group@example.com"] == []

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_members_list_response(
        self, mock_get_service, mock_batch_request, google_member_factory
    ):
        """Test batch member retrieval when response is a list."""
        group_keys = ["group@example.com"]
        members = google_member_factory(2, domain="example.com")

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_batch_request.return_value = {
            "results": {
                "group@example.com": members  # Direct list instead of dict with 'members' key
            }
        }

        result = gdn.get_batch_members(group_keys)

        assert result["group@example.com"] == members


class TestListMembers:
    """Test cases for list_members function."""

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_list_members_success(self, mock_execute, google_member_factory):
        """Test successful member listing."""
        expected_members = google_member_factory(3)
        mock_execute.return_value = expected_members

        result = gdn.list_members("test-group@example.com")

        assert result == expected_members
        mock_execute.assert_called_once_with(
            "admin",
            "directory_v1",
            "members",
            "list",
            scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
            non_critical=True,
            groupKey="test-group@example.com",
        )


class TestHasMember:
    """Test cases for has_member function."""

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_has_member_true(self, mock_execute):
        """Test has_member returns True when member exists."""
        mock_execute.return_value = True

        result = gdn.has_member("group@example.com", "user@example.com")

        assert result is True

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_has_member_false(self, mock_execute):
        """Test has_member returns False when member doesn't exist."""
        mock_execute.return_value = False

        result = gdn.has_member("group@example.com", "user@example.com")

        assert result is False


class TestInsertMember:
    """Test cases for insert_member function."""

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_insert_member_simple(self, mock_execute):
        """Test simple member insertion."""
        expected_response = {
            "kind": "admin#directory#member",
            "email": "user@example.com",
        }
        mock_execute.return_value = expected_response

        result = gdn.insert_member("group@example.com", "user@example.com")

        assert result == expected_response
        mock_execute.assert_called_once_with(
            "admin",
            "directory_v1",
            "members",
            "insert",
            scopes=["https://www.googleapis.com/auth/admin.directory.group"],
            non_critical=True,
            groupKey="group@example.com",
            body={"email": "user@example.com", "role": "MEMBER", "type": "USER"},
        )

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_insert_member_with_custom_body(self, mock_execute):
        """Test member insertion with custom body."""
        custom_body = {"email": "user@example.com", "role": "OWNER", "type": "USER"}
        mock_execute.return_value = {"kind": "admin#directory#member"}

        gdn.insert_member(
            "group@example.com", "user@example.com", member_body=custom_body
        )

        mock_execute.assert_called_once_with(
            "admin",
            "directory_v1",
            "members",
            "insert",
            scopes=["https://www.googleapis.com/auth/admin.directory.group"],
            non_critical=True,
            groupKey="group@example.com",
            body=custom_body,
        )


class TestListGroupsWithMembers:
    """Test cases for list_groups_with_members function."""

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch("integrations.google_workspace.google_directory_next.get_batch_members")
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_success(
        self,
        mock_list_groups,
        mock_get_batch_members,
        mock_get_batch_users,
        google_group_factory,
        google_member_factory,
        google_user_factory,
    ):
        """Test successful listing of groups with members."""
        # Setup test data
        groups = google_group_factory(2, domain="example.com")
        groups[0]["email"] = "group1@example.com"
        groups[1]["email"] = "group2@example.com"

        members1 = google_member_factory(2, prefix="user1-", domain="example.com")
        members2 = google_member_factory(2, prefix="user2-", domain="example.com")

        users = google_user_factory(4, domain="example.com")
        # Ensure email consistency
        members1[0]["email"] = "user1-user-email1@example.com"
        members1[1]["email"] = "user1-user-email2@example.com"
        members2[0]["email"] = "user2-user-email1@example.com"
        members2[1]["email"] = "user2-user-email2@example.com"

        users[0]["primaryEmail"] = "user1-user-email1@example.com"
        users[1]["primaryEmail"] = "user1-user-email2@example.com"
        users[2]["primaryEmail"] = "user2-user-email1@example.com"
        users[3]["primaryEmail"] = "user2-user-email2@example.com"

        # Setup mocks
        mock_list_groups.return_value = groups
        mock_get_batch_members.return_value = {
            "group1@example.com": members1,
            "group2@example.com": members2,
        }
        mock_get_batch_users.return_value = {
            "user1-user-email1@example.com": users[0],
            "user1-user-email2@example.com": users[1],
            "user2-user-email1@example.com": users[2],
            "user2-user-email2@example.com": users[3],
        }

        result = gdn.list_groups_with_members()

        # Assertions
        assert len(result) == 2
        assert result[0]["email"] == "group1@example.com"
        assert result[1]["email"] == "group2@example.com"
        assert len(result[0]["members"]) == 2
        assert len(result[1]["members"]) == 2

        # Check that user details are included
        for member in result[0]["members"]:
            assert "user_details" in member
            assert "primaryEmail" in member  # Flattened from user_details
            assert "name" in member  # Flattened from user_details

    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_no_groups(self, mock_list_groups):
        """Test listing groups with members when no groups exist."""
        mock_list_groups.return_value = []

        result = gdn.list_groups_with_members()

        assert result == []

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch("integrations.google_workspace.google_directory_next.get_batch_members")
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_with_filters(
        self,
        mock_list_groups,
        mock_get_batch_members,
        mock_get_batch_users,
        google_group_factory,
    ):
        """Test listing groups with members using filters."""
        groups = google_group_factory(3, domain="example.com")
        groups[0]["email"] = "aws-group1@example.com"
        groups[1]["email"] = "aws-group2@example.com"
        groups[2]["email"] = "other-group@example.com"

        mock_list_groups.return_value = groups
        mock_get_batch_members.return_value = {
            "aws-group1@example.com": [],
            "aws-group2@example.com": [],
        }
        mock_get_batch_users.return_value = {}

        # Filter for AWS groups only
        filters = [lambda g: g["email"].startswith("aws-")]
        result = gdn.list_groups_with_members(
            groups_filters=filters, tolerate_errors=True
        )

        assert len(result) == 2
        assert all(group["email"].startswith("aws-") for group in result)

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch("integrations.google_workspace.google_directory_next.get_batch_members")
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_tolerate_errors(
        self,
        mock_list_groups,
        mock_get_batch_members,
        mock_get_batch_users,
        google_group_factory,
    ):
        """Test listing groups with members with tolerate_errors=True."""
        groups = google_group_factory(1, domain="example.com")
        groups[0]["email"] = "empty-group@example.com"

        mock_list_groups.return_value = groups
        mock_get_batch_members.return_value = {"empty-group@example.com": []}
        mock_get_batch_users.return_value = {}

        result = gdn.list_groups_with_members(tolerate_errors=True)

        assert len(result) == 1
        assert result[0]["email"] == "empty-group@example.com"
        assert result[0]["members"] == []
        assert "error" in result[0]

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch("integrations.google_workspace.google_directory_next.get_batch_members")
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_exclude_empty_groups(
        self,
        mock_list_groups,
        mock_get_batch_members,
        mock_get_batch_users,
        google_group_factory,
    ):
        """Test that empty groups are excluded when tolerate_errors=False."""
        groups = google_group_factory(1, domain="example.com")
        groups[0]["email"] = "empty-group@example.com"

        mock_list_groups.return_value = groups
        mock_get_batch_members.return_value = {"empty-group@example.com": []}
        mock_get_batch_users.return_value = {}

        result = gdn.list_groups_with_members(tolerate_errors=False)

        assert len(result) == 0

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch("integrations.google_workspace.google_directory_next.get_batch_members")
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_user_details_flattening(
        self,
        mock_list_groups,
        mock_get_batch_members,
        mock_get_batch_users,
        google_group_factory,
        google_member_factory,
        google_user_factory,
    ):
        """Test that user details are properly flattened into member objects."""
        # Setup test data
        groups = google_group_factory(1, domain="example.com")
        groups[0]["email"] = "test-group@example.com"

        members = google_member_factory(1, domain="example.com")
        members[0]["email"] = "test@example.com"

        users = google_user_factory(1, domain="example.com")
        users[0]["primaryEmail"] = "test@example.com"
        users[0]["name"] = {"givenName": "Test", "familyName": "User"}
        users[0]["orgUnitPath"] = "/TestOU"

        # Setup mocks
        mock_list_groups.return_value = groups
        mock_get_batch_members.return_value = {"test-group@example.com": members}
        mock_get_batch_users.return_value = {"test@example.com": users[0]}

        result = gdn.list_groups_with_members()

        # Verify flattening
        member = result[0]["members"][0]
        assert "user_details" in member  # Original nested structure preserved
        assert "primaryEmail" in member  # Flattened key
        assert "name" in member  # Flattened key
        assert "orgUnitPath" in member  # Flattened key
        assert member["primaryEmail"] == "test@example.com"
        assert member["name"] == {"givenName": "Test", "familyName": "User"}

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch("integrations.google_workspace.google_directory_next.get_batch_members")
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_no_key_conflicts(
        self,
        mock_list_groups,
        mock_get_batch_members,
        mock_get_batch_users,
        google_group_factory,
        google_member_factory,
        google_user_factory,
    ):
        """Test that existing member keys are not overwritten during flattening."""
        # Setup test data
        groups = google_group_factory(1, domain="example.com")
        groups[0]["email"] = "test-group@example.com"

        members = google_member_factory(1, domain="example.com")
        members[0]["email"] = "test@example.com"
        members[0]["role"] = "OWNER"  # Existing key that should not be overwritten

        users = google_user_factory(1, domain="example.com")
        users[0]["primaryEmail"] = "test@example.com"
        users[0]["role"] = "USER_ROLE"  # This should not overwrite the member's role

        # Setup mocks
        mock_list_groups.return_value = groups
        mock_get_batch_members.return_value = {"test-group@example.com": members}
        mock_get_batch_users.return_value = {"test@example.com": users[0]}

        result = gdn.list_groups_with_members()

        # Verify no overwrite
        member = result[0]["members"][0]
        assert member["role"] == "OWNER"  # Original member role preserved
        assert (
            member["user_details"]["role"] == "USER_ROLE"
        )  # User role in nested structure
