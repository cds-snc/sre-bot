"""Unit tests for DirectoryClient."""

from unittest.mock import Mock

from googleapiclient.errors import HttpError

from infrastructure.clients.google_workspace.directory import DirectoryClient
from infrastructure.operations.status import OperationStatus


class TestDirectoryClientUsers:
    """Test DirectoryClient user operations."""

    def test_get_user_success(self, mock_session_provider: Mock):
        """Test successful user retrieval."""
        # Setup mock service
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {
            "primaryEmail": "user@example.com",
            "name": {"fullName": "Test User"},
            "id": "123456789",
        }
        mock_service.users().get.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        # Execute
        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_user("user@example.com")

        # Verify
        assert result.is_success
        assert result.data is not None
        assert result.data["primaryEmail"] == "user@example.com"
        assert result.data["name"]["fullName"] == "Test User"
        mock_service.users().get.assert_called_once_with(userKey="user@example.com")

    def test_get_user_with_delegation(self, mock_session_provider: Mock):
        """Test user retrieval with domain-wide delegation."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {"primaryEmail": "user@example.com"}
        mock_service.users().get.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_user(
            "user@example.com", delegated_email="admin@example.com"
        )

        assert result.is_success
        mock_session_provider.get_service.assert_called_once()
        call_kwargs = mock_session_provider.get_service.call_args[1]
        assert call_kwargs["delegated_user_email"] == "admin@example.com"

    def test_list_users_single_page(self, mock_session_provider: Mock):
        """Test listing users with single page response."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {
            "users": [
                {"primaryEmail": "user1@example.com", "id": "1"},
                {"primaryEmail": "user2@example.com", "id": "2"},
            ]
        }
        mock_service.users().list.return_value = mock_request
        mock_service.users().list_next.return_value = None
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.list_users()

        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 2
        assert result.data[0]["primaryEmail"] == "user1@example.com"
        mock_service.users().list.assert_called_once_with(customer="my_customer")

    def test_list_users_pagination(self, mock_session_provider: Mock):
        """Test listing users with automatic pagination."""
        mock_service = Mock()

        # Page 1
        mock_request1 = Mock()
        mock_request1.execute.return_value = {
            "users": [{"primaryEmail": "user1@example.com", "id": "1"}],
            "nextPageToken": "token123",
        }

        # Page 2
        mock_request2 = Mock()
        mock_request2.execute.return_value = {
            "users": [{"primaryEmail": "user2@example.com", "id": "2"}]
        }

        mock_service.users().list.return_value = mock_request1
        mock_service.users().list_next.side_effect = [mock_request2, None]
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.list_users()

        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 2
        assert result.data[0]["primaryEmail"] == "user1@example.com"
        assert result.data[1]["primaryEmail"] == "user2@example.com"

    def test_list_users_with_custom_customer(self, mock_session_provider: Mock):
        """Test listing users with custom customer ID."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {"users": []}
        mock_service.users().list.return_value = mock_request
        mock_service.users().list_next.return_value = None
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.list_users(customer="custom_customer")

        assert result.is_success
        mock_service.users().list.assert_called_once_with(customer="custom_customer")

    def test_list_users_with_kwargs(self, mock_session_provider: Mock):
        """Test listing users with additional parameters."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {"users": []}
        mock_service.users().list.return_value = mock_request
        mock_service.users().list_next.return_value = None
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.list_users(maxResults=10, query="name:John")

        assert result.is_success
        mock_service.users().list.assert_called_once_with(
            customer="my_customer", maxResults=10, query="name:John"
        )

    def test_create_user_success(self, mock_session_provider: Mock):
        """Test successful user creation."""
        mock_service = Mock()
        mock_request = Mock()
        created_user = {
            "primaryEmail": "newuser@example.com",
            "name": {"fullName": "New User"},
            "id": "999",
        }
        mock_request.execute.return_value = created_user
        mock_service.users().insert.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        user_body = {
            "primaryEmail": "newuser@example.com",
            "name": {"givenName": "New", "familyName": "User"},
            "password": "SecurePass123!",
        }

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.create_user(user_body)

        assert result.is_success
        assert result.data is not None
        assert result.data["primaryEmail"] == "newuser@example.com"
        mock_service.users().insert.assert_called_once_with(body=user_body)

    def test_update_user_success(self, mock_session_provider: Mock):
        """Test successful user update."""
        mock_service = Mock()
        mock_request = Mock()
        updated_user = {
            "primaryEmail": "user@example.com",
            "suspended": True,
        }
        mock_request.execute.return_value = updated_user
        mock_service.users().update.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        update_body = {"suspended": True}

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.update_user("user@example.com", update_body)

        assert result.is_success
        assert result.data is not None
        assert result.data["suspended"] is True
        mock_service.users().update.assert_called_once_with(
            userKey="user@example.com", body=update_body
        )

    def test_delete_user_success(self, mock_session_provider: Mock):
        """Test successful user deletion."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = None
        mock_service.users().delete.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.delete_user("user@example.com")

        assert result.is_success
        mock_service.users().delete.assert_called_once_with(userKey="user@example.com")


class TestDirectoryClientGroups:
    """Test DirectoryClient group operations."""

    def test_get_group_success(self, mock_session_provider: Mock):
        """Test successful group retrieval."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {
            "email": "group@example.com",
            "name": "Test Group",
            "id": "123456789",
        }
        mock_service.groups().get.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_group("group@example.com")

        assert result.is_success
        assert result.data is not None
        assert result.data["email"] == "group@example.com"
        assert result.data["name"] == "Test Group"
        mock_service.groups().get.assert_called_once_with(groupKey="group@example.com")

    def test_list_groups_single_page(self, mock_session_provider: Mock):
        """Test listing groups with single page response."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {
            "groups": [
                {"email": "group1@example.com", "id": "1"},
                {"email": "group2@example.com", "id": "2"},
            ]
        }
        mock_service.groups().list.return_value = mock_request
        mock_service.groups().list_next.return_value = None
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.list_groups()

        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 2
        assert result.data[0]["email"] == "group1@example.com"

    def test_list_groups_pagination(self, mock_session_provider: Mock):
        """Test listing groups with automatic pagination."""
        mock_service = Mock()

        # Page 1
        mock_request1 = Mock()
        mock_request1.execute.return_value = {
            "groups": [{"email": "group1@example.com", "id": "1"}],
            "nextPageToken": "token123",
        }

        # Page 2
        mock_request2 = Mock()
        mock_request2.execute.return_value = {
            "groups": [{"email": "group2@example.com", "id": "2"}]
        }

        mock_service.groups().list.return_value = mock_request1
        mock_service.groups().list_next.side_effect = [mock_request2, None]
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.list_groups()

        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 2

    def test_create_group_success(self, mock_session_provider: Mock):
        """Test successful group creation."""
        mock_service = Mock()
        mock_request = Mock()
        created_group = {
            "email": "newgroup@example.com",
            "name": "New Group",
            "id": "999",
        }
        mock_request.execute.return_value = created_group
        mock_service.groups().insert.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        group_body = {
            "email": "newgroup@example.com",
            "name": "New Group",
        }

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.create_group(group_body)

        assert result.is_success
        assert result.data is not None
        assert result.data["email"] == "newgroup@example.com"
        mock_service.groups().insert.assert_called_once_with(body=group_body)

    def test_update_group_success(self, mock_session_provider: Mock):
        """Test successful group update."""
        mock_service = Mock()
        mock_request = Mock()
        updated_group = {
            "email": "group@example.com",
            "name": "Updated Name",
        }
        mock_request.execute.return_value = updated_group
        mock_service.groups().update.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        update_body = {"name": "Updated Name"}

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.update_group("group@example.com", update_body)

        assert result.is_success
        assert result.data is not None
        assert result.data["name"] == "Updated Name"
        mock_service.groups().update.assert_called_once_with(
            groupKey="group@example.com", body=update_body
        )

    def test_delete_group_success(self, mock_session_provider: Mock):
        """Test successful group deletion."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = None
        mock_service.groups().delete.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.delete_group("group@example.com")

        assert result.is_success
        mock_service.groups().delete.assert_called_once_with(
            groupKey="group@example.com"
        )


class TestDirectoryClientMembers:
    """Test DirectoryClient member operations."""

    def test_list_members_single_page(self, mock_session_provider: Mock):
        """Test listing members with single page response."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {
            "members": [
                {"email": "user1@example.com", "role": "MEMBER"},
                {"email": "user2@example.com", "role": "OWNER"},
            ]
        }
        mock_service.members().list.return_value = mock_request
        mock_service.members().list_next.return_value = None
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.list_members("group@example.com")

        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 2
        assert result.data[0]["email"] == "user1@example.com"
        assert result.data[1]["role"] == "OWNER"
        mock_service.members().list.assert_called_once_with(
            groupKey="group@example.com"
        )

    def test_list_members_pagination(self, mock_session_provider: Mock):
        """Test listing members with automatic pagination."""
        mock_service = Mock()

        # Page 1
        mock_request1 = Mock()
        mock_request1.execute.return_value = {
            "members": [{"email": "user1@example.com", "role": "MEMBER"}],
            "nextPageToken": "token123",
        }

        # Page 2
        mock_request2 = Mock()
        mock_request2.execute.return_value = {
            "members": [{"email": "user2@example.com", "role": "OWNER"}]
        }

        mock_service.members().list.return_value = mock_request1
        mock_service.members().list_next.side_effect = [mock_request2, None]
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.list_members("group@example.com")

        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 2

    def test_add_member_success(self, mock_session_provider: Mock):
        """Test successful member addition."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {
            "email": "newmember@example.com",
            "role": "MEMBER",
            "id": "999",
        }
        mock_service.members().insert.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        member_body = {
            "email": "newmember@example.com",
            "role": "MEMBER",
        }

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.add_member("group@example.com", member_body)

        assert result.is_success
        assert result.data is not None
        assert result.data["email"] == "newmember@example.com"
        mock_service.members().insert.assert_called_once_with(
            groupKey="group@example.com", body=member_body
        )

    def test_remove_member_success(self, mock_session_provider: Mock):
        """Test successful member removal."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = None
        mock_service.members().delete.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.remove_member("group@example.com", "user@example.com")

        assert result.is_success
        mock_service.members().delete.assert_called_once_with(
            groupKey="group@example.com", memberKey="user@example.com"
        )


class TestDirectoryClientErrorHandling:
    """Test DirectoryClient error handling."""

    def test_get_user_not_found(self, mock_session_provider: Mock):
        """Test user not found error handling."""

        mock_service = Mock()
        mock_request = Mock()
        # Simulate 404 Not Found
        http_error = HttpError(
            resp=Mock(status=404), content=b'{"error": "User not found"}'
        )
        mock_request.execute.side_effect = http_error
        mock_service.users().get.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_user("nonexistent@example.com")

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR

    def test_list_users_permission_denied(self, mock_session_provider: Mock):
        """Test permission denied error handling."""
        from googleapiclient.errors import HttpError

        mock_service = Mock()
        mock_request = Mock()
        # Simulate 403 Forbidden
        http_error = HttpError(
            resp=Mock(status=403), content=b'{"error": "Permission denied"}'
        )
        mock_request.execute.side_effect = http_error
        mock_service.users().list.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.list_users()

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR


class TestDirectoryClientMembershipChecks:
    """Test DirectoryClient membership check operations."""

    def test_get_member_success(self, mock_session_provider: Mock):
        """Test successful member retrieval."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {
            "email": "member@example.com",
            "role": "MEMBER",
            "type": "USER",
        }
        mock_service.members().get.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_member("group@example.com", "member@example.com")

        assert result.is_success
        assert result.data is not None
        assert result.data["email"] == "member@example.com"
        assert result.data["role"] == "MEMBER"
        mock_service.members().get.assert_called_once_with(
            groupKey="group@example.com", memberKey="member@example.com"
        )

    def test_has_member_success(self, mock_session_provider: Mock):
        """Test successful membership check."""
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {"isMember": True}
        mock_service.members().hasMember.return_value = mock_request
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.has_member("group@example.com", "member@example.com")

        assert result.is_success
        assert result.data is not None
        assert result.data["isMember"] is True
        mock_service.members().hasMember.assert_called_once_with(
            groupKey="group@example.com", memberKey="member@example.com"
        )


class TestDirectoryClientBatchOperations:
    """Test DirectoryClient batch operations."""

    def test_get_batch_users_success(self, mock_session_provider: Mock):
        """Test successful batch user retrieval."""
        mock_service = Mock()
        mock_batch = Mock()

        # Capture the callback when new_batch_http_request is called
        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        mock_service.new_batch_http_request = capture_callback

        # Setup batch execution
        def batch_execute():
            # Simulate successful batch responses
            cb = callback_holder["callback"]
            cb(
                "user1@example.com",
                {"primaryEmail": "user1@example.com", "name": {"fullName": "User 1"}},
                None,
            )
            cb(
                "user2@example.com",
                {"primaryEmail": "user2@example.com", "name": {"fullName": "User 2"}},
                None,
            )

        mock_batch.execute = batch_execute
        mock_batch.add = Mock()  # Mock the add method
        mock_service.users().get.return_value = Mock()  # API request objects
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_batch_users(["user1@example.com", "user2@example.com"])

        assert result.is_success
        assert result.data is not None
        assert "user1@example.com" in result.data
        assert "user2@example.com" in result.data

    def test_get_batch_groups_success(self, mock_session_provider: Mock):
        """Test successful batch group retrieval."""
        mock_service = Mock()
        mock_batch = Mock()

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        mock_service.new_batch_http_request = capture_callback

        def batch_execute():
            cb = callback_holder["callback"]
            cb(
                "group1@example.com",
                {"email": "group1@example.com", "name": "Group 1"},
                None,
            )
            cb(
                "group2@example.com",
                {"email": "group2@example.com", "name": "Group 2"},
                None,
            )

        mock_batch.execute = batch_execute
        mock_batch.add = Mock()
        mock_service.groups().get.return_value = Mock()
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_batch_groups(["group1@example.com", "group2@example.com"])

        assert result.is_success
        assert result.data is not None
        assert "group1@example.com" in result.data
        assert "group2@example.com" in result.data

    def test_get_batch_members_for_user_success(self, mock_session_provider: Mock):
        """Test successful batch member retrieval for a user."""
        mock_service = Mock()
        mock_batch = Mock()

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        mock_service.new_batch_http_request = capture_callback

        def batch_execute():
            cb = callback_holder["callback"]
            cb(
                "group1@example.com",
                {"email": "user@example.com", "role": "MEMBER"},
                None,
            )
            cb(
                "group2@example.com",
                {"email": "user@example.com", "role": "OWNER"},
                None,
            )

        mock_batch.execute = batch_execute
        mock_batch.add = Mock()
        mock_service.members().get.return_value = Mock()
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_batch_members_for_user(
            ["group1@example.com", "group2@example.com"], "user@example.com"
        )

        assert result.is_success
        assert result.data is not None
        assert result.data["group1@example.com"]["role"] == "MEMBER"
        assert result.data["group2@example.com"]["role"] == "OWNER"

    def test_get_batch_group_members_success(self, mock_session_provider: Mock):
        """Test successful batch group members retrieval."""
        mock_service = Mock()
        mock_batch = Mock()

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        mock_service.new_batch_http_request = capture_callback

        def batch_execute():
            cb = callback_holder["callback"]
            cb(
                "group1@example.com",
                {
                    "members": [
                        {"email": "user1@example.com", "role": "MEMBER"},
                        {"email": "user2@example.com", "role": "OWNER"},
                    ]
                },
                None,
            )
            cb(
                "group2@example.com",
                {"members": [{"email": "user3@example.com", "role": "MEMBER"}]},
                None,
            )

        mock_batch.execute = batch_execute
        mock_batch.add = Mock()
        mock_service.members().list.return_value = Mock()
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_batch_group_members(
            ["group1@example.com", "group2@example.com"]
        )

        assert result.is_success
        assert result.data is not None
        assert len(result.data["group1@example.com"]) == 2
        assert len(result.data["group2@example.com"]) == 1


class TestDirectoryClientAdvancedFeatures:
    """Test DirectoryClient advanced features."""

    def test_list_groups_with_members_basic(self, mock_session_provider: Mock):
        """Test basic list_groups_with_members operation."""
        from infrastructure.clients.google_workspace.directory import (
            ListGroupsWithMembersRequest,
        )

        # Setup mocks for list_groups
        mock_service = Mock()
        mock_groups_request = Mock()
        mock_groups_response = Mock()
        mock_groups_response.get.return_value = [
            {"email": "group1@example.com", "name": "Group 1"},
            {"email": "group2@example.com", "name": "Group 2"},
        ]
        mock_groups_request.execute.return_value = mock_groups_response
        mock_service.groups().list.return_value = mock_groups_request
        mock_service.groups().list_next.return_value = None

        # Setup batch for members
        mock_batch = Mock()

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        mock_service.new_batch_http_request = capture_callback

        def batch_execute():
            cb = callback_holder["callback"]
            cb(
                "group1@example.com",
                {"members": [{"email": "user1@example.com", "role": "MEMBER"}]},
                None,
            )
            cb(
                "group2@example.com",
                {"members": [{"email": "user2@example.com", "role": "OWNER"}]},
                None,
            )

        mock_batch.execute = batch_execute
        mock_batch.add = Mock()
        mock_service.members().list.return_value = Mock()

        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        request = ListGroupsWithMembersRequest(include_users_details=False)
        result = client.list_groups_with_members(request)

        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 2
        assert result.data[0]["email"] == "group1@example.com"
        assert len(result.data[0]["members"]) == 1
        assert result.data[1]["email"] == "group2@example.com"
        assert len(result.data[1]["members"]) == 1

    def test_list_groups_with_members_with_group_filters(
        self, mock_session_provider: Mock
    ):
        """Test list_groups_with_members with group filters."""
        from infrastructure.clients.google_workspace.directory import (
            ListGroupsWithMembersRequest,
        )

        mock_service = Mock()
        mock_groups_request = Mock()
        mock_groups_response = Mock()
        mock_groups_response.get.return_value = [
            {"email": "team-alpha@example.com", "name": "Team Alpha"},
            {"email": "admin@example.com", "name": "Admin"},
            {"email": "team-beta@example.com", "name": "Team Beta"},
        ]
        mock_groups_request.execute.return_value = mock_groups_response
        mock_service.groups().list.return_value = mock_groups_request
        mock_service.groups().list_next.return_value = None

        mock_batch = Mock()

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        mock_service.new_batch_http_request = capture_callback

        def batch_execute():
            cb = callback_holder["callback"]
            cb(
                "team-alpha@example.com",
                {"members": [{"email": "user1@example.com"}]},
                None,
            )
            cb(
                "team-beta@example.com",
                {"members": [{"email": "user2@example.com"}]},
                None,
            )

        mock_batch.execute = batch_execute
        mock_batch.add = Mock()
        mock_service.members().list.return_value = Mock()

        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        request = ListGroupsWithMembersRequest(
            groups_filters=[lambda g: g.get("email", "").startswith("team-")],
            include_users_details=False,
        )
        result = client.list_groups_with_members(request)

        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 2
        assert all(g["email"].startswith("team-") for g in result.data)

    def test_list_groups_with_members_with_member_filters(
        self, mock_session_provider: Mock
    ):
        """Test list_groups_with_members with member filters."""
        from infrastructure.clients.google_workspace.directory import (
            ListGroupsWithMembersRequest,
        )

        mock_service = Mock()
        mock_groups_request = Mock()
        mock_groups_response = Mock()
        mock_groups_response.get.return_value = [
            {"email": "group1@example.com", "name": "Group 1"},
            {"email": "group2@example.com", "name": "Group 2"},
        ]
        mock_groups_request.execute.return_value = mock_groups_response
        mock_service.groups().list.return_value = mock_groups_request
        mock_service.groups().list_next.return_value = None

        mock_batch = Mock()

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        mock_service.new_batch_http_request = capture_callback

        def batch_execute():
            cb = callback_holder["callback"]
            cb(
                "group1@example.com",
                {
                    "members": [
                        {"email": "user1@example.com", "role": "MEMBER"},
                        {"email": "user2@example.com", "role": "OWNER"},
                    ]
                },
                None,
            )
            cb(
                "group2@example.com",
                {"members": [{"email": "user3@example.com", "role": "MEMBER"}]},
                None,
            )

        mock_batch.execute = batch_execute
        mock_batch.add = Mock()
        mock_service.members().list.return_value = Mock()

        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        # Filter for groups that have at least one OWNER
        request = ListGroupsWithMembersRequest(
            member_filters=[lambda m: m.get("role") == "OWNER"],
            include_users_details=False,
        )
        result = client.list_groups_with_members(request)

        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0]["email"] == "group1@example.com"

    def test_list_groups_with_members_exclude_empty(self, mock_session_provider: Mock):
        """Test list_groups_with_members with exclude_empty_groups option."""
        from infrastructure.clients.google_workspace.directory import (
            ListGroupsWithMembersRequest,
        )

        mock_service = Mock()
        mock_groups_request = Mock()
        mock_groups_response = Mock()
        mock_groups_response.get.return_value = [
            {"email": "group1@example.com", "name": "Group 1"},
            {"email": "group2@example.com", "name": "Group 2"},
        ]
        mock_groups_request.execute.return_value = mock_groups_response
        mock_service.groups().list.return_value = mock_groups_request
        mock_service.groups().list_next.return_value = None

        mock_batch = Mock()

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        mock_service.new_batch_http_request = capture_callback

        def batch_execute():
            cb = callback_holder["callback"]
            cb(
                "group1@example.com",
                {"members": [{"email": "user1@example.com", "role": "MEMBER"}]},
                None,
            )
            cb("group2@example.com", {"members": []}, None)  # Empty group

        mock_batch.execute = batch_execute
        mock_batch.add = Mock()
        mock_service.members().list.return_value = Mock()

        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        request = ListGroupsWithMembersRequest(
            exclude_empty_groups=True, include_users_details=False
        )
        result = client.list_groups_with_members(request)

        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0]["email"] == "group1@example.com"

    def test_list_groups_with_members_with_user_details(
        self, mock_session_provider: Mock
    ):
        """Test list_groups_with_members with user details enrichment."""
        from infrastructure.clients.google_workspace.directory import (
            ListGroupsWithMembersRequest,
        )

        mock_service = Mock()

        # Mock groups response
        mock_groups_request = Mock()
        mock_groups_response = Mock()
        mock_groups_response.get.return_value = [
            {"email": "group1@example.com", "name": "Group 1"},
        ]
        mock_groups_request.execute.return_value = mock_groups_response
        mock_service.groups().list.return_value = mock_groups_request
        mock_service.groups().list_next.return_value = None

        # Mock batch for members
        mock_batch = Mock()
        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        mock_service.new_batch_http_request = capture_callback

        batch_call_count = [0]

        def batch_execute():
            cb = callback_holder["callback"]
            batch_call_count[0] += 1

            # First batch: get group members
            if batch_call_count[0] == 1:
                cb(
                    "group1@example.com",
                    {
                        "members": [
                            {"email": "user1@example.com", "role": "MEMBER"},
                            {"email": "user2@example.com", "role": "OWNER"},
                        ]
                    },
                    None,
                )
            # Second batch: get user details
            elif batch_call_count[0] == 2:
                cb(
                    "user1@example.com",
                    {
                        "primaryEmail": "user1@example.com",
                        "name": {"fullName": "User One"},
                    },
                    None,
                )
                cb(
                    "user2@example.com",
                    {
                        "primaryEmail": "user2@example.com",
                        "name": {"fullName": "User Two"},
                    },
                    None,
                )

        mock_batch.execute = batch_execute
        mock_batch.add = Mock()
        mock_service.members().list.return_value = Mock()
        mock_service.users().get.return_value = Mock()

        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        request = ListGroupsWithMembersRequest(include_users_details=True)
        result = client.list_groups_with_members(request)

        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 1
        group = result.data[0]
        assert len(group["members"]) == 2
        # Verify user details were enriched
        assert "user" in group["members"][0]
        assert group["members"][0]["user"]["name"]["fullName"] == "User One"
        assert "user" in group["members"][1]
        assert group["members"][1]["user"]["name"]["fullName"] == "User Two"

    def test_list_groups_with_members_no_matching_groups(
        self, mock_session_provider: Mock
    ):
        """Test list_groups_with_members when filters return no groups."""
        from infrastructure.clients.google_workspace.directory import (
            ListGroupsWithMembersRequest,
        )

        mock_service = Mock()
        mock_groups_request = Mock()
        mock_groups_response = Mock()
        mock_groups_response.get.return_value = [
            {"email": "group1@example.com", "name": "Group 1"},
            {"email": "group2@example.com", "name": "Group 2"},
        ]
        mock_groups_request.execute.return_value = mock_groups_response
        mock_service.groups().list.return_value = mock_groups_request
        mock_service.groups().list_next.return_value = None

        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )

        # Filter that excludes all groups
        request = ListGroupsWithMembersRequest(
            groups_filters=[lambda g: "nomatch" in g.get("email", "")],
            include_users_details=False,
        )
        result = client.list_groups_with_members(request)

        assert result.is_success
        assert result.data == []
        assert result.message == "No groups found matching filters"

    def test_list_groups_with_members_batch_failure(self, mock_session_provider: Mock):
        """Test list_groups_with_members handles batch operation failure gracefully."""
        from infrastructure.clients.google_workspace.directory import (
            ListGroupsWithMembersRequest,
        )

        mock_service = Mock()

        # Mock successful groups response
        mock_groups_request = Mock()
        mock_groups_response = Mock()
        mock_groups_response.get.return_value = [
            {"email": "group1@example.com", "name": "Group 1"},
        ]
        mock_groups_request.execute.return_value = mock_groups_response
        mock_service.groups().list.return_value = mock_groups_request
        mock_service.groups().list_next.return_value = None

        # Mock batch that fails
        mock_batch = Mock()
        mock_batch.execute.side_effect = RuntimeError("Batch execution failed")
        mock_batch.add = Mock()
        mock_service.new_batch_http_request.return_value = mock_batch
        mock_service.members().list.return_value = Mock()

        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        request = ListGroupsWithMembersRequest(include_users_details=False)
        result = client.list_groups_with_members(request)

        # Batch failure should propagate as error, not success
        assert not result.is_success
        assert "Batch execution failed" in result.message


class TestDirectoryClientBatchOperationEdgeCases:
    """Test edge cases in batch operations."""

    def test_get_batch_users_with_batch_failure(self, mock_session_provider: Mock):
        """Test get_batch_users propagates batch execution failure as error."""
        mock_service = Mock()
        mock_batch = Mock()
        mock_batch.execute.side_effect = RuntimeError("Network error")
        mock_batch.add = Mock()
        mock_service.new_batch_http_request.return_value = mock_batch
        mock_service.users().get.return_value = Mock()
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_batch_users(["user1@example.com", "user2@example.com"])

        # Batch failure should propagate as error
        assert not result.is_success
        assert result.error_code == "GOOGLE_API_ERROR"

    def test_get_batch_groups_with_batch_failure(self, mock_session_provider: Mock):
        """Test get_batch_groups propagates batch execution failure as error."""
        mock_service = Mock()
        mock_batch = Mock()
        mock_batch.execute.side_effect = RuntimeError("Network error")
        mock_batch.add = Mock()
        mock_service.new_batch_http_request.return_value = mock_batch
        mock_service.groups().get.return_value = Mock()
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_batch_groups(["group1@example.com", "group2@example.com"])

        # Batch failure should propagate as error
        assert not result.is_success
        assert result.error_code == "GOOGLE_API_ERROR"

    def test_get_batch_members_for_user_with_batch_failure(
        self, mock_session_provider: Mock
    ):
        """Test get_batch_members_for_user propagates batch execution failure as error."""
        mock_service = Mock()
        mock_batch = Mock()
        mock_batch.execute.side_effect = RuntimeError("Network error")
        mock_batch.add = Mock()
        mock_service.new_batch_http_request.return_value = mock_batch
        mock_service.members().get.return_value = Mock()
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_batch_members_for_user(
            ["group1@example.com", "group2@example.com"], "user@example.com"
        )

        # Batch failure should propagate as error
        assert not result.is_success
        assert result.error_code == "GOOGLE_API_ERROR"

    def test_get_batch_group_members_with_batch_failure(
        self, mock_session_provider: Mock
    ):
        """Test get_batch_group_members propagates batch execution failure as error."""
        mock_service = Mock()
        mock_batch = Mock()
        mock_batch.execute.side_effect = RuntimeError("Network error")
        mock_batch.add = Mock()
        mock_service.new_batch_http_request.return_value = mock_batch
        mock_service.members().list.return_value = Mock()
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_batch_group_members(
            ["group1@example.com", "group2@example.com"]
        )

        # Batch failure should propagate as error
        assert not result.is_success
        assert result.error_code == "GOOGLE_API_ERROR"

    def test_get_batch_group_members_handles_various_result_types(
        self, mock_session_provider: Mock
    ):
        """Test get_batch_group_members handles dict, None, and other result types."""
        mock_service = Mock()
        mock_batch = Mock()

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        mock_service.new_batch_http_request = capture_callback

        def batch_execute():
            cb = callback_holder["callback"]
            # Valid dict response
            cb(
                "group1@example.com",
                {"members": [{"email": "user1@example.com"}]},
                None,
            )
            # None response (group not found)
            cb("group2@example.com", None, None)
            # Non-dict response (edge case)
            cb("group3@example.com", "unexpected", None)

        mock_batch.execute = batch_execute
        mock_batch.add = Mock()
        mock_service.members().list.return_value = Mock()
        mock_session_provider.get_service.return_value = mock_service

        client = DirectoryClient(
            session_provider=mock_session_provider, default_customer_id="my_customer"
        )
        result = client.get_batch_group_members(
            ["group1@example.com", "group2@example.com", "group3@example.com"]
        )

        assert result.is_success
        assert result.data is not None
        # Valid dict result should have members
        assert len(result.data["group1@example.com"]) == 1
        # None result should return empty list
        assert result.data["group2@example.com"] == []
        # Non-dict result should return empty list
        assert result.data["group3@example.com"] == []
