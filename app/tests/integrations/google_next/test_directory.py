""""Unit tests for the Google Directory API."""

# import unittest
from unittest.mock import MagicMock, call, patch

import pytest
from integrations.google_next import directory
from integrations.google_next.directory import GoogleDirectory


@pytest.fixture(scope="class")
@patch("integrations.google_next.directory.get_google_service")
def google_directory(mock_get_google_service) -> GoogleDirectory:
    scopes = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]
    delegated_email = "email@test.com"
    mock_get_google_service.return_value = MagicMock()
    return GoogleDirectory(scopes, delegated_email)


@pytest.mark.usefixtures(
    "google_groups", "google_group_members", "google_users", "google_groups_w_users"
)
class TestGoogleDirectory:
    @pytest.fixture(autouse=True)
    def setup(self, google_directory: GoogleDirectory):
        self.google_directory = google_directory

    def test_init_without_scopes_and_service(self):
        """Test initialization without scopes and service raises ValueError."""
        with pytest.raises(
            ValueError, match="Either scopes or a service must be provided."
        ):
            GoogleDirectory(delegated_email="email@test.com")

    @patch(
        "integrations.google_next.directory.GOOGLE_DELEGATED_ADMIN_EMAIL",
        new="default@test.com",
    )
    @patch("integrations.google_next.directory.get_google_service")
    def test_init_without_delegated_email_and_service(self, mock_get_google_service):
        """Test initialization without delegated email and service uses default email."""
        mock_get_google_service.return_value = MagicMock()
        google_directory = GoogleDirectory(
            scopes=["https://www.googleapis.com/auth/admin.directory.user.readonly"]
        )
        assert google_directory.delegated_email == "default@test.com"

    @patch("integrations.google_next.directory.get_google_service")
    def test_get_directory_service(self, mock_get_google_service):
        """Test get_directory_service returns a service."""
        mock_get_google_service.return_value = MagicMock()
        service = self.google_directory._get_directory_service()
        assert service is not None
        mock_get_google_service.assert_called_once_with(
            "admin",
            "directory_v1",
            self.google_directory.scopes,
            self.google_directory.delegated_email,
        )

    @patch("integrations.google_next.directory.execute_google_api_call")
    def test_get_user(self, mock_execute_google_api_call: MagicMock):
        """Test get_user returns a user."""
        mock_execute_google_api_call.return_value = {
            "id": "test_user_id",
            "name": "test_user",
            "email": "user.name@domain.com",
        }
        result = self.google_directory.get_user("test_user_id")
        expected_result = {
            "id": "test_user_id",
            "name": "test_user",
            "email": "user.name@domain.com",
        }
        assert result == expected_result
        mock_execute_google_api_call.assert_called_once_with(
            self.google_directory.service, "users", "get", userKey="test_user_id"
        )

    @patch("integrations.google_next.directory.execute_google_api_call")
    def test_list_users_handles_customer_param(self, mock_execute_google_api_call):
        """Test list_users returns users with customer param."""
        mock_execute_google_api_call.return_value = [
            {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
            {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
        ]
        result = self.google_directory.list_users(customer="test_customer_id")
        expected_result = [
            {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
            {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
        ]
        assert result == expected_result
        mock_execute_google_api_call.assert_called_once_with(
            self.google_directory.service,
            "users",
            "list",
            paginate=True,
            customer="test_customer_id",
        )

    @patch(
        "integrations.google_next.directory.GOOGLE_WORKSPACE_CUSTOMER_ID",
        new="default_id",
    )
    @patch("integrations.google_next.directory.execute_google_api_call")
    def test_list_users(self, mock_execute_google_api_call):
        """Test list_users returns users."""
        mock_execute_google_api_call.return_value = [
            {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
            {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
        ]
        result = self.google_directory.list_users()
        expected_result = [
            {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
            {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
        ]
        assert result == expected_result
        mock_execute_google_api_call.assert_called_once_with(
            self.google_directory.service,
            "users",
            "list",
            paginate=True,
            customer="default_id",
        )

    @patch("integrations.google_next.directory.execute_google_api_call")
    def test_get_group(self, mock_execute_google_api_call):
        """Test get_group returns a group."""
        mock_execute_google_api_call.return_value = {
            "id": "test_group_id",
            "name": "test_group",
            "email": "test_email@domain.com",
        }
        expected_result = {
            "id": "test_group_id",
            "name": "test_group",
            "email": "test_email@domain.com",
        }
        result = self.google_directory.get_group("test_group_id")
        assert result == expected_result
        mock_execute_google_api_call.assert_called_once_with(
            self.google_directory.service, "groups", "get", groupKey="test_group_id"
        )

    @patch("integrations.google_next.directory.execute_google_api_call")
    def test_list_groups_handles_customer_param(self, mock_execute_google_api_call):
        """Test list_groups returns groups with customer param."""
        results = [
            {"id": "test_group_id", "name": "test_group", "email": "email@domain.com"},
            {
                "id": "test_group_id2",
                "name": "test_group2",
                "email": "email2@domain.com",
            },
        ]
        mock_execute_google_api_call.return_value = results
        result = self.google_directory.list_groups(customer="test_customer_id")
        assert result == results
        mock_execute_google_api_call.assert_called_once_with(
            self.google_directory.service,
            "groups",
            "list",
            paginate=True,
            customer="test_customer_id",
        )

    @patch(
        "integrations.google_next.directory.GOOGLE_WORKSPACE_CUSTOMER_ID",
        new="default_id",
    )
    @patch("integrations.google_next.directory.execute_google_api_call")
    def test_list_groups(self, mock_execute_google_api_call):
        """Test list_groups returns groups."""
        results = [
            {"id": "test_group_id", "name": "test_group", "email": "email@domain.com"},
            {
                "id": "test_group_id2",
                "name": "test_group2",
                "email": "email2@domain.com",
            },
        ]
        mock_execute_google_api_call.return_value = results
        result = self.google_directory.list_groups()
        assert result == results
        mock_execute_google_api_call.assert_called_once_with(
            self.google_directory.service,
            "groups",
            "list",
            paginate=True,
            customer="default_id",
        )

    @patch("integrations.google_next.directory.execute_google_api_call")
    def test_list_group_members(self, mock_execute_google_api_call):
        """Test list_group_members returns group members."""
        results = [
            {"id": "test_member_id", "email": "member@domain.com"},
            {"id": "test_member_id2", "email": "member2@domain.com"},
        ]
        mock_execute_google_api_call.return_value = results
        result = self.google_directory.list_group_members("test_group_id")
        assert result == results
        mock_execute_google_api_call.assert_called_once_with(
            self.google_directory.service,
            "members",
            "list",
            paginate=True,
            groupKey="test_group_id",
        )

    def test_list_groups_with_members(
        self,
        google_groups,
        google_group_members,
        google_users,
        google_groups_w_users,
    ):
        groups = google_groups(2)
        group_members = [[], google_group_members(2)]
        users = google_users(2)
        groups_with_users = google_groups_w_users(2, 2)

        groups_with_users.remove(groups_with_users[0])

        self.google_directory.list_groups = MagicMock()
        self.google_directory.list_groups.return_value = groups
        self.google_directory.list_group_members = MagicMock()
        self.google_directory.list_group_members.side_effect = group_members
        self.google_directory.list_users = MagicMock()
        self.google_directory.list_users.return_value = users

        result = self.google_directory.list_groups_with_members()
        assert result == groups_with_users

    def test_list_groups_with_members_without_groups(
        self,
    ):
        self.google_directory.list_groups = MagicMock()
        self.google_directory.list_groups.return_value = []

        result = self.google_directory.list_groups_with_members()
        assert result == []

    def test_list_groups_with_members_filtered_by_condition(
        self,
        google_groups,
        google_group_members,
        google_users,
        google_groups_w_users,
    ):
        groups = google_groups(2, prefix="test-")
        groups_to_filter_out = google_groups(4)[2:]
        groups.extend(groups_to_filter_out)
        group_members = [[], google_group_members(2)]
        users = google_users(2)
        groups_with_users = google_groups_w_users(4, 2, group_prefix="test-")[:2]
        groups_with_users.remove(groups_with_users[0])

        with patch(
            "integrations.google_next.directory.filters.filter_by_condition"
        ) as mock_filter_by_condition:
            mock_filter_by_condition.return_value = groups[:2]

        self.google_directory.list_groups = MagicMock()
        self.google_directory.list_groups.return_value = groups
        self.google_directory.list_group_members = MagicMock()
        self.google_directory.list_group_members.side_effect = group_members
        self.google_directory.list_users = MagicMock()
        self.google_directory.list_users.return_value = users

        groups_filters = [lambda group: "test-" in group["name"]]

        response = self.google_directory.list_groups_with_members(
            groups_filters=groups_filters
        )
        assert response == groups_with_users
        assert mock_filter_by_condition.called_once_with(groups, groups_filters)
        assert self.google_directory.list_group_members.call_count == 2
        assert self.google_directory.list_users.call_count == 1

    @patch("integrations.google_next.directory.GoogleDirectory.get_members_details")
    @patch("integrations.google_next.directory.retry_request")
    @patch("integrations.google_next.directory.logger")
    def test_list_groups_with_members_updates_group_with_group_error(
        self, mock_logger, mock_retry_request, mock_get_members_details
    ):
        groups = [
            {"id": "test_group_id1", "name": "test_group1", "email": "group_email1"},
            {"id": "test_group_id2", "name": "test_group2", "email": "group_email2"},
        ]

        group_members = [
            [{"id": "test_member_id1", "email": "email1"}],
            [{"id": "test_member_id2", "email": "email2"}],
        ]

        users = [
            {"id": "test_user_id1", "name": "test_user1", "email": "email1"},
            {"id": "test_user_id2", "name": "test_user2", "email": "email2"},
        ]

        expected_output = [
            {
                "id": "test_group_id1",
                "name": "test_group1",
                "email": "group_email1",
                "error": "Error getting members: Retry Exception",
            },
            {
                "id": "test_group_id2",
                "name": "test_group2",
                "email": "group_email2",
                "members": [
                    {
                        "id": "test_member_id2",
                        "email": "email2",
                        "name": "test_user2",
                        "primaryEmail": "email2",
                    }
                ],
            },
        ]

        self.google_directory.list_groups = MagicMock()
        self.google_directory.list_groups.return_value = groups
        self.google_directory.list_group_members = MagicMock()
        self.google_directory.list_group_members.side_effect = group_members
        self.google_directory.list_users = MagicMock()
        self.google_directory.list_users.return_value = users
        mock_retry_request.side_effect = [
            Exception("Retry Exception"),
            group_members[1],
        ]
        mock_get_members_details.side_effect = [
            [
                {
                    "id": "test_member_id2",
                    "email": "email2",
                    "name": "test_user2",
                    "primaryEmail": "email2",
                }
            ],
        ]
        with pytest.raises(Exception):
            assert self.google_directory.list_groups_with_members() == expected_output

        mock_logger.info.assert_has_calls(
            [
                call("Found 2 groups."),
                call("Found 2 groups after filtering."),
                call("Getting members for group: group_email1"),
                call("Getting members for group: group_email2"),
            ]
        )
        mock_logger.warning.assert_called_once_with(
            "Error getting members for group group_email1: Retry Exception"
        )
        mock_logger.error.assert_not_called()

    @patch("integrations.google_next.directory.GoogleDirectory.get_members_details")
    @patch("integrations.google_next.directory.retry_request")
    @patch("integrations.google_next.directory.logger")
    def test_list_groups_with_members_updates_group_with_user_error(
        self, mock_logger, mock_retry_request, mock_get_members_details
    ):

        groups = [
            {"id": "test_group_id1", "name": "test_group1", "email": "group_email1"},
            {"id": "test_group_id2", "name": "test_group2", "email": "group_email2"},
        ]

        group_members1 = [
            [{"id": "test_member_id1", "email": "email1"}],
            [{"id": "test_member_id2", "email": "email2"}],
        ]
        group_members2 = [
            [{"id": "test_member_id2", "email": "email2"}],
            [{"id": "test_member_id3", "email": "email3"}],
        ]

        users = [
            {"id": "test_user_id2", "name": "test_user2", "email": "email2"},
            {"id": "test_user_id3", "name": "test_user3", "email": "email3"},
        ]

        expected_output = [
            {
                "id": "test_group_id1",
                "name": "test_group1",
                "email": "group_email1",
                "members": [
                    {
                        "id": "test_member_id1",
                        "email": "email1",
                        "error": "User details not found",
                    },
                    {
                        "id": "test_member_id2",
                        "email": "email2",
                        "name": "test_user2",
                        "primaryEmail": "email2",
                    },
                ],
                "error": "Error getting members details.",
            },
            {
                "id": "test_group_id2",
                "name": "test_group2",
                "email": "group_email2",
                "members": [
                    {
                        "id": "test_member_id2",
                        "email": "email2",
                        "name": "test_user2",
                        "primaryEmail": "email2",
                    },
                    {
                        "id": "test_member_id3",
                        "email": "email3",
                        "name": "test_user3",
                        "primaryEmail": "email3",
                    },
                ],
            },
        ]
        self.google_directory.list_groups = MagicMock()
        self.google_directory.list_groups.return_value = groups
        self.google_directory.list_group_members = MagicMock()
        self.google_directory.list_users = MagicMock()
        self.google_directory.list_users.return_value = users
        mock_retry_request.side_effect = [group_members1, group_members2]
        mock_get_members_details.side_effect = [
            [
                {
                    "id": "test_member_id1",
                    "email": "email1",
                    "error": "User details not found",
                },
                {
                    "id": "test_member_id2",
                    "email": "email2",
                    "name": "test_user2",
                    "primaryEmail": "email2",
                },
            ],
            [
                {
                    "id": "test_member_id2",
                    "email": "email2",
                    "name": "test_user2",
                    "primaryEmail": "email2",
                },
                {
                    "id": "test_member_id3",
                    "email": "email3",
                    "name": "test_user3",
                    "primaryEmail": "email3",
                },
            ],
        ]

        assert self.google_directory.list_groups_with_members() == expected_output

        mock_logger.info.assert_has_calls(
            [
                call("Found 2 groups."),
                call("Found 2 groups after filtering."),
                call("Getting members for group: group_email1"),
                call("Getting members for group: group_email2"),
            ]
        )
        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_not_called()

    def test_get_members_details(self):
        members = [
            {"email": "email1", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
            {"email": "email2", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
        ]

        users = [
            {"name": "user1", "primaryEmail": "email1"},
            {"name": "user2", "primaryEmail": "email2"},
        ]

        expected_result = [
            {
                "email": "email1",
                "role": "MEMBER",
                "type": "USER",
                "status": "ACTIVE",
                "name": "user1",
                "primaryEmail": "email1",
            },
            {
                "email": "email2",
                "role": "MEMBER",
                "type": "USER",
                "status": "ACTIVE",
                "name": "user2",
                "primaryEmail": "email2",
            },
        ]

        assert (
            self.google_directory.get_members_details(members, users) == expected_result
        )

    @patch("integrations.google_next.directory.logger")
    def test_get_members_details_handles_user_not_found(self, mock_logger):
        members = [
            {"email": "email1", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
            {"email": "email2", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
        ]

        users = [
            {"name": "user2", "primaryEmail": "email2"},
        ]

        expected_result = [
            {
                "email": "email1",
                "role": "MEMBER",
                "type": "USER",
                "status": "ACTIVE",
                "error": "User details not found",
            },
            {
                "email": "email2",
                "role": "MEMBER",
                "type": "USER",
                "status": "ACTIVE",
                "name": "user2",
                "primaryEmail": "email2",
            },
        ]

        assert (
            self.google_directory.get_members_details(members, users) == expected_result
        )
        mock_logger.info.assert_has_calls(
            [
                call("Getting user details for member: email1"),
                call("Getting user details for member: email2"),
            ]
        )
        mock_logger.warning.assert_called_once_with(
            "User details not found for member: email1"
        )
