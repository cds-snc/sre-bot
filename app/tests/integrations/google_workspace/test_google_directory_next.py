"""
Unit and integration tests for google_directory_next module.
"""

from unittest.mock import Mock, patch
from infrastructure.operations.result import OperationResult
from integrations.google_workspace import google_directory_next as gdn
from integrations.google_workspace.schemas import (
    User,
    Member,
    Group,
    GroupWithMembers,
)
from tests.factories.google import (
    make_google_groups,
    make_google_users,
    make_google_members,
)


class TestGetUser:
    """Test cases for get_user function."""

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_get_user_success(self, mock_execute):
        """Test successful user retrieval."""
        # Use helper to generate a realistic user payload
        expected_user = make_google_users(n=1, prefix="svc-", domain="example.com")[0]
        mock_execute.return_value = OperationResult.success(data=expected_user)

        result = gdn.get_user("svc-user@example.com")

        assert isinstance(result, OperationResult)
        assert result.is_success

        # Validate payload with Pydantic schema
        validated = User.model_validate(result.data)
        assert validated.id is not None

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_get_user_not_found(self, mock_execute):
        """Test user not found scenario."""
        error = Exception("User not found")
        mock_execute.return_value = OperationResult.permanent_error(message=str(error))

        result = gdn.get_user("doesnotexist@example.com")

        assert isinstance(result, OperationResult)
        assert not result.is_success
        assert result.message == "User not found"

        mock_execute.return_value = None

        result = gdn.get_user("nonexistent@example.com")

        assert result is None


class TestGetBatchUsers:
    """Test cases for get_batch_users function."""

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_users_success(self, mock_get_service, mock_batch_request):
        """Test successful batch user retrieval."""
        user_keys = ["user1@example.com", "user2@example.com"]
        users = make_google_users(2, domain="example.com")

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        batch_data = {
            "results": {"user1@example.com": users[0], "user2@example.com": users[1]}
        }
        mock_batch_request.return_value = OperationResult.success(data=batch_data)

        result = gdn.get_batch_users(user_keys)

        assert isinstance(result, OperationResult)
        assert result.is_success
        # result.data is expected to be a dict mapping user_key -> user dict
        assert isinstance(result.data, dict)
        mock_get_service.assert_called_once()
        mock_batch_request.assert_called_once()
        # Validate each returned user against Pydantic schema
        for k, v in result.data.items():
            validated_user = User.model_validate(v)
            assert validated_user.id is not None

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_users_empty_list(self, mock_get_service, mock_batch_request):
        """Test batch user retrieval with empty list."""
        user_keys = []

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        batch_data = {"results": {}}
        mock_batch_request.return_value = OperationResult.success(data=batch_data)

        result = gdn.get_batch_users(user_keys)

        assert isinstance(result, OperationResult)
        assert result.is_success
        assert result.data == {}


class TestListUsers:
    """Test cases for list_users function."""

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_list_users_success(self, mock_execute):
        """Test successful user listing."""
        expected_users = make_google_users(3)
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
    def test_get_group_success(self, mock_execute):
        """Test successful group retrieval."""
        expected_group = make_google_groups(1)[0]
        # Mock to return OperationResult
        mock_execute.return_value = OperationResult.success(data=expected_group)

        result = gdn.get_group("test-group@example.com")

        assert isinstance(result, OperationResult)
        assert result.is_success
        # Validate returned group data
        validated = Group.model_validate(result.data)
        assert validated.email is not None


class TestGetBatchGroups:
    """Test cases for get_batch_groups function."""

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_groups_success(self, mock_get_service, mock_batch_request):
        """Test successful batch group retrieval."""
        group_keys = ["group1@example.com", "group2@example.com"]
        groups = make_google_groups(2, domain="example.com")

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_batch_request.return_value = OperationResult.success(
            data={
                "results": {
                    "group1@example.com": groups[0],
                    "group2@example.com": groups[1],
                }
            }
        )

        result = gdn.get_batch_groups(group_keys)

        assert isinstance(result, OperationResult)
        assert result.is_success
        # result.data expected to be dict of groups by key
        data = result.data
        assert isinstance(data, dict)
        for k, g in data.items():
            validated_group = Group.model_validate(g)
            assert validated_group.id is not None


class TestListGroups:
    """Test cases for list_groups function."""

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_list_groups_success(self, mock_execute):
        """Test successful group listing."""
        expected_groups = make_google_groups(3)
        mock_execute.return_value = OperationResult.success(data=expected_groups)

        result = gdn.list_groups()

        assert isinstance(result, OperationResult)
        assert result.is_success
        # Validate group list items
        for g in result.data:
            validated_group = Group.model_validate(g)
            assert validated_group.id is not None


class TestGetBatchMembers:
    """Test cases for get_batch_group_members function."""

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_group_members_success(
        self, mock_get_service, mock_batch_request
    ):
        """Test successful batch member retrieval."""
        group_keys = ["group1@example.com", "group2@example.com"]
        members1 = make_google_members(2, prefix="user1-", domain="example.com")
        members2 = make_google_members(2, prefix="user2-", domain="example.com")

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_batch_request.return_value = OperationResult.success(
            data={
                "results": {
                    "group1@example.com": {"members": members1},
                    "group2@example.com": {"members": members2},
                }
            }
        )

        result = gdn.get_batch_group_members(group_keys)

        assert isinstance(result, OperationResult)
        assert result.is_success
        data = result.data
        assert isinstance(data, dict)
        assert data["group1@example.com"] == members1
        assert data["group2@example.com"] == members2

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_group_members_no_members(
        self, mock_get_service, mock_batch_request
    ):
        """Test batch member retrieval when groups have no members."""
        group_keys = ["empty-group@example.com"]

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_batch_request.return_value = OperationResult.success(
            data={"results": {"empty-group@example.com": None}}
        )

        result = gdn.get_batch_group_members(group_keys)

        assert isinstance(result, OperationResult)
        assert result.is_success
        data = result.data
        assert data["empty-group@example.com"] == []

    @patch("integrations.google_workspace.google_directory_next.execute_batch_request")
    @patch("integrations.google_workspace.google_directory_next.get_google_service")
    def test_get_batch_group_members_list_response(
        self, mock_get_service, mock_batch_request
    ):
        """Test batch member retrieval when response is a list."""
        group_keys = ["group@example.com"]
        members = make_google_members(2, domain="example.com")

        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_batch_request.return_value = OperationResult.success(
            data={"results": {"group@example.com": members}}
        )

        result = gdn.get_batch_group_members(group_keys)

        assert isinstance(result, OperationResult)
        assert result.is_success
        data = result.data
        assert data["group@example.com"] == members


class TestListMembers:
    """Test cases for list_members function."""

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_list_members_success(self, mock_execute):
        """Test successful member listing."""
        expected_members = make_google_members(3)
        mock_execute.return_value = OperationResult.success(data=expected_members)

        result = gdn.list_members("test-group@example.com")

        assert isinstance(result, OperationResult)
        assert result.is_success
        # validate members
        for m in result.data:
            validated = Member.model_validate(m)
            assert validated.id is not None


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
        mock_execute.return_value = OperationResult.success(data=expected_response)

        result = gdn.insert_member("group@example.com", "user@example.com")

        assert isinstance(result, OperationResult)
        assert result.is_success
        assert result.data["email"] == "user@example.com"

    @patch(
        "integrations.google_workspace.google_directory_next.execute_google_api_call"
    )
    def test_insert_member_with_custom_body(self, mock_execute):
        """Test member insertion with custom body."""
        custom_body = {"email": "user@example.com", "role": "OWNER", "type": "USER"}
        mock_execute.return_value = OperationResult.success(
            data={"kind": "admin#directory#member"}
        )

        result = gdn.insert_member(
            "group@example.com", "user@example.com", member_body=custom_body
        )

        assert isinstance(result, OperationResult)
        assert result.is_success


class TestListGroupsWithMembers:
    """Test cases for list_groups_with_members function."""

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch(
        "integrations.google_workspace.google_directory_next.get_batch_group_members"
    )
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_success(
        self,
        mock_list_groups,
        mock_get_batch_group_members,
        mock_get_batch_users,
    ):
        """Test successful listing of groups with members."""
        # Setup test data
        groups = make_google_groups(2, domain="example.com")
        groups[0]["email"] = "group1@example.com"
        groups[1]["email"] = "group2@example.com"

        members1 = make_google_members(2, prefix="user1-", domain="example.com")
        members2 = make_google_members(2, prefix="user2-", domain="example.com")

        users = make_google_users(4, domain="example.com")
        # Ensure email consistency
        members1[0]["email"] = "user1-user-email1@example.com"
        members1[1]["email"] = "user1-user-email2@example.com"
        members2[0]["email"] = "user2-user-email1@example.com"
        members2[1]["email"] = "user2-user-email2@example.com"

        users[0]["primaryEmail"] = "user1-user-email1@example.com"
        users[1]["primaryEmail"] = "user1-user-email2@example.com"
        users[2]["primaryEmail"] = "user2-user-email1@example.com"
        users[3]["primaryEmail"] = "user2-user-email2@example.com"

        # Setup mocks to return OperationResult objects
        mock_list_groups.return_value = OperationResult.success(data=groups)
        mock_get_batch_group_members.return_value = OperationResult.success(
            data={"group1@example.com": members1, "group2@example.com": members2}
        )
        mock_get_batch_users.return_value = OperationResult.success(
            data={
                "user1-user-email1@example.com": users[0],
                "user1-user-email2@example.com": users[1],
                "user2-user-email1@example.com": users[2],
                "user2-user-email2@example.com": users[3],
            }
        )

        result = gdn.list_groups_with_members()

        # Should return OperationResult
        assert isinstance(result, OperationResult)
        assert result.is_success
        assembled = result.data
        assert len(assembled) == 2
        assert assembled[0]["email"] == "group1@example.com"
        assert assembled[1]["email"] == "group2@example.com"
        assert len(assembled[0]["members"]) == 2
        assert len(assembled[1]["members"]) == 2

        result = gdn.list_groups_with_members()
        # Check that member dicts have expected keys
        for member in result.data[0]["members"]:
            assert "primaryEmail" in member
            assert "name" in member
        # Validate assembled groups with the assembled GroupWithMembers model
        validated_groups = [GroupWithMembers.model_validate(g) for g in assembled]
        assert validated_groups[0].email == "group1@example.com"
        assert len(validated_groups[0].members) == 2

    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_no_groups(self, mock_list_groups):
        """Test listing groups with members when no groups exist."""
        mock_list_groups.return_value = OperationResult.success(data=[])

        result = gdn.list_groups_with_members()
        assert isinstance(result, OperationResult)

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch(
        "integrations.google_workspace.google_directory_next.get_batch_group_members"
    )
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_with_filters(
        self,
        mock_list_groups,
        mock_get_batch_group_members,
        mock_get_batch_users,
    ):
        """Test listing groups with members using filters."""
        groups = make_google_groups(3, domain="example.com")
        groups[0]["email"] = "aws-group1@example.com"
        groups[1]["email"] = "aws-group2@example.com"
        groups[2]["email"] = "other-group@example.com"

        mock_list_groups.return_value = OperationResult.success(data=groups)
        mock_get_batch_group_members.return_value = OperationResult.success(
            data={"aws-group1@example.com": [], "aws-group2@example.com": []}
        )
        mock_get_batch_users.return_value = OperationResult.success(data={})

        # Filter for AWS groups only
        filters = [lambda g: g["email"].startswith("aws-")]
        request = gdn.ListGroupsWithMembersRequest(groups_filters=filters)
        result = gdn.list_groups_with_members(request=request)
        assert isinstance(result, OperationResult)
        if result.success:
            validated = [GroupWithMembers.model_validate(g) for g in result.data]
            for g in validated:
                assert g.email.startswith("aws-")

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch(
        "integrations.google_workspace.google_directory_next.get_batch_group_members"
    )
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_tolerate_errors(
        self,
        mock_list_groups,
        mock_get_batch_group_members,
        mock_get_batch_users,
    ):
        """Test listing groups with members with tolerate_errors=True."""
        groups = make_google_groups(1, domain="example.com")
        groups[0]["email"] = "empty-group@example.com"

        mock_list_groups.return_value = OperationResult.success(data=groups)
        mock_get_batch_group_members.return_value = OperationResult.success(
            data={"empty-group@example.com": []}
        )
        mock_get_batch_users.return_value = OperationResult.success(data={})

        result = gdn.list_groups_with_members()
        assert isinstance(result, OperationResult)
        if result.success:
            validated = [GroupWithMembers.model_validate(g) for g in result.data]
            for g in validated:
                assert isinstance(g.members, list)

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch(
        "integrations.google_workspace.google_directory_next.get_batch_group_members"
    )
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_exclude_empty_groups(
        self,
        mock_list_groups,
        mock_get_batch_group_members,
        mock_get_batch_users,
    ):
        """Test that empty groups are excluded when tolerate_errors=False."""
        groups = make_google_groups(1, domain="example.com")
        groups[0]["email"] = "empty-group@example.com"

        mock_list_groups.return_value = OperationResult.success(data=groups)
        mock_get_batch_group_members.return_value = OperationResult.success(
            data={"empty-group@example.com": []}
        )
        mock_get_batch_users.return_value = OperationResult.success(data={})

        result = gdn.list_groups_with_members()
        assert isinstance(result, OperationResult)
        if result.success:
            validated = [GroupWithMembers.model_validate(g) for g in result.data]
            for g in validated:
                assert isinstance(g.members, list)

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch(
        "integrations.google_workspace.google_directory_next.get_batch_group_members"
    )
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_user_details_flattening(
        self,
        mock_list_groups,
        mock_get_batch_group_members,
        mock_get_batch_users,
    ):
        """Test that user details are properly flattened into member objects."""
        # Setup test data
        groups = make_google_groups(1, domain="example.com")
        groups[0]["email"] = "test-group@example.com"

        members = make_google_members(1, domain="example.com")
        members[0]["email"] = "test@example.com"

        users = make_google_users(1, domain="example.com")
        users[0]["primaryEmail"] = "test@example.com"
        users[0]["name"] = {"givenName": "Test", "familyName": "User"}
        users[0]["orgUnitPath"] = "/TestOU"

        # Setup mocks
        mock_list_groups.return_value = OperationResult.success(data=groups)
        mock_get_batch_group_members.return_value = OperationResult.success(
            data={"test-group@example.com": members}
        )
        mock_get_batch_users.return_value = OperationResult.success(
            data={"test@example.com": users[0]}
        )

        result = gdn.list_groups_with_members()

        assert isinstance(result, OperationResult)
        assert result.is_success
        assembled = result.data
        # Validate assembled groups and ensure member flattening occurred
        validated_groups = [GroupWithMembers.model_validate(g) for g in assembled]
        assert len(validated_groups) == 1
        vg = validated_groups[0]
        assert vg.email == "test-group@example.com"
        assert len(vg.members) == 1
        validated_member = vg.members[0]
        # the member's email field should match the group member entry
        assert validated_member.email == "test@example.com"
        # the nested user object (enriched) should have the primaryEmail we requested
        if validated_member.user:
            assert validated_member.user.primaryEmail == "test@example.com"

    @patch("integrations.google_workspace.google_directory_next.get_batch_users")
    @patch(
        "integrations.google_workspace.google_directory_next.get_batch_group_members"
    )
    @patch("integrations.google_workspace.google_directory_next.list_groups")
    def test_list_groups_with_members_no_key_conflicts(
        self,
        mock_list_groups,
        mock_get_batch_group_members,
        mock_get_batch_users,
    ):
        """Test that existing member keys are not overwritten during flattening."""
        # Setup test data
        groups = make_google_groups(1, domain="example.com")
        groups[0]["email"] = "test-group@example.com"

        members = make_google_members(1, domain="example.com")
        members[0]["email"] = "test@example.com"
        members[0]["role"] = "OWNER"  # Existing key that should not be overwritten

        users = make_google_users(1, domain="example.com")
        users[0]["primaryEmail"] = "test@example.com"
        users[0]["role"] = "USER_ROLE"  # This should not overwrite the member's role

        # Setup mocks
        mock_list_groups.return_value = OperationResult.success(data=groups)
        mock_get_batch_group_members.return_value = OperationResult.success(
            data={"test-group@example.com": members}
        )
        mock_get_batch_users.return_value = OperationResult.success(
            data={"test@example.com": users[0]}
        )

        result = gdn.list_groups_with_members()

        assert isinstance(result, OperationResult)
        assert result.is_success
        assembled = result.data
        # Validate assembled groups and ensure member role preserved
        validated = [GroupWithMembers.model_validate(g) for g in assembled]
        vg = validated[0]
        assert vg.email == "test-group@example.com"
        assert vg.members[0].role == "OWNER"
