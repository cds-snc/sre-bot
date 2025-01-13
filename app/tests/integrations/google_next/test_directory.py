""""Unit tests for the Google Directory API."""

from unittest.mock import MagicMock, call, patch

import pytest
from integrations.google_next import directory

GOOGLE_WORKSPACE_CUSTOMER_ID = "test_customer_id"


@patch("integrations.google_next.directory.get_google_service")
def test_get_directory_service_returns_service(mock_get_google_service: MagicMock):
    """Test get_directory_service returns a service."""
    mock_get_google_service.return_value = MagicMock()
    mock_delegated_email = "email@test.com"
    assert (
        directory.get_directory_service(delegated_email=mock_delegated_email)
        is not None
    )
    mock_get_google_service.assert_called_once_with(
        "admin", "directory_v1", None, "email@test.com"
    )


@patch("integrations.google_next.directory.GOOGLE_DELEGATED_ADMIN_EMAIL", new="test_email")
@patch("integrations.google_next.directory.get_google_service")
def test_get_directory_service_returns_service_with_default_email(
    mock_get_google_service: MagicMock,
):
    """Test get_directory_service returns a service with default email."""
    mock_get_google_service.return_value = MagicMock()
    assert directory.get_directory_service() is not None
    mock_get_google_service.assert_called_once_with(
        "admin", "directory_v1", None, "test_email"
    )


@patch("integrations.google_next.directory.execute_google_api_call")
def test_get_user_returns_user(mock_execute_google_api_call: MagicMock):
    """Test get_user returns a user."""

    mock_service = MagicMock()
    mock_execute_google_api_call.return_value = {
        "id": "test_user_id",
        "name": "test_user",
        "email": "user.name@domain.com",
    }

    result = directory.get_user(mock_service, "test_user_id")

    expected_result = {
        "id": "test_user_id",
        "name": "test_user",
        "email": "user.name@domain.com",
    }
    assert result == expected_result
    mock_execute_google_api_call.assert_called_once_with(
        mock_service, "users", "get", userKey="test_user_id"
    )


@patch(
    "integrations.google_next.directory.GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="test_customer_id",
)
@patch("integrations.google_next.directory.execute_google_api_call")
def test_list_users_returns_users(execute_google_api_call_mock: MagicMock):
    mock_service = MagicMock()

    results = [
        {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
    ]

    execute_google_api_call_mock.return_value = results

    assert directory.list_users(mock_service) == results

    execute_google_api_call_mock.assert_called_once_with(
        mock_service,
        "users",
        "list",
        paginate=True,
        customer="test_customer_id",
    )


@patch(
    "integrations.google_next.directory.GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="test_customer_id",
)
@patch("integrations.google_next.directory.execute_google_api_call")
def test_list_users_handles_customer_param(execute_google_api_call_mock: MagicMock):
    mock_service = MagicMock()

    results = [
        {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
    ]

    execute_google_api_call_mock.return_value = results

    assert directory.list_users(mock_service, customer="custom_id") == results

    execute_google_api_call_mock.assert_called_once_with(
        mock_service,
        "users",
        "list",
        paginate=True,
        customer="custom_id",
    )


@patch("integrations.google_next.directory.execute_google_api_call")
def test_get_group_returns_group(mock_execute_google_api_call: MagicMock):
    """Test get_group returns a group."""
    mock_service = MagicMock()
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

    assert expected_result == directory.get_group(mock_service, "test_group_id")
    mock_execute_google_api_call.assert_called_once_with(
        mock_service, "groups", "get", groupKey="test_group_id"
    )


@patch(
    "integrations.google_next.directory.GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="test_customer_id",
)
@patch("integrations.google_next.directory.execute_google_api_call")
def test_list_groups_returns_groups(mock_execute_google_api_call: MagicMock):
    """Test list_groups returns groups."""
    mock_service = MagicMock()
    results = [
        {"id": "test_group_id", "name": "test_group", "email": "email@domain.com"},
        {"id": "test_group_id2", "name": "test_group2", "email": "email2@domain.com"},
    ]
    mock_execute_google_api_call.return_value = results

    assert directory.list_groups(mock_service) == results

    mock_execute_google_api_call.assert_called_once_with(
        mock_service, "groups", "list", paginate=True, customer="test_customer_id"
    )


@patch(
    "integrations.google_next.directory.GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="test_customer_id",
)
@patch("integrations.google_next.directory.execute_google_api_call")
def test_list_groups_handles_customer_param(mock_execute_google_api_call: MagicMock):
    """Test list_groups returns groups."""
    mock_service = MagicMock()
    results = [
        {"id": "test_group_id", "name": "test_group", "email": "email@domain.com"},
        {"id": "test_group_id2", "name": "test_group2", "email": "email2@domain.com"},
    ]
    mock_execute_google_api_call.return_value = results

    assert directory.list_groups(mock_service, customer="custom_id") == results

    mock_execute_google_api_call.assert_called_once_with(
        mock_service, "groups", "list", paginate=True, customer="custom_id"
    )


@patch("integrations.google_next.directory.execute_google_api_call")
def test_list_group_members_returns_group_members(
    mock_execute_google_api_call: MagicMock,
):
    """Test list_group_members returns group members."""
    mock_service = MagicMock()
    results = [
        {"id": "test_member_id", "email": "member@domain.com"},
        {"id": "test_member_id2", "email": "member2@domain.com"},
    ]

    mock_execute_google_api_call.return_value = results

    assert directory.list_group_members(mock_service, "test_group_id") == results

    mock_execute_google_api_call.assert_called_once_with(
        mock_service, "members", "list", paginate=True, groupKey="test_group_id"
    )


@patch("integrations.google_next.directory.list_groups")
@patch("integrations.google_next.directory.list_group_members")
@patch("integrations.google_next.directory.list_users")
def test_list_groups_with_members_returns_groups_with_members(
    mock_list_users: MagicMock,
    mock_list_group_members: MagicMock,
    mock_list_groups: MagicMock,
    google_groups,
    google_group_members,
    google_users,
    google_groups_w_users,
):
    """Test list_groups_with_members returns groups with members."""
    mock_service = MagicMock()
    groups = google_groups(2)
    group_members = [[], google_group_members(2)]
    users = google_users(2)
    groups_with_users = google_groups_w_users(2, 2)

    groups_with_users.remove(groups_with_users[0])

    mock_list_groups.return_value = groups
    mock_list_group_members.side_effect = group_members
    mock_list_users.return_value = users

    assert directory.list_groups_with_members(mock_service) == groups_with_users


@patch("integrations.google_next.directory.list_groups")
@patch("integrations.google_next.directory.list_group_members")
@patch("integrations.google_next.directory.list_users")
def test_list_groups_with_members_returns_groups_with_no_members(
    mock_list_user: MagicMock,
    mock_list_group_members: MagicMock,
    mock_list_groups: MagicMock,
):
    """Test list_groups_with_members returns groups with members."""

    mock_service = MagicMock()
    mock_list_groups.return_value = []

    assert directory.list_groups_with_members(mock_service) == []


@patch("integrations.google_next.directory.filters.filter_by_condition")
@patch("integrations.google_next.directory.list_groups")
@patch("integrations.google_next.directory.list_group_members")
@patch("integrations.google_next.directory.list_users")
def test_list_groups_with_members_filtered_by_condition(
    mock_list_users,
    mock_list_group_members,
    mock_list_groups,
    mock_filter_by_condition,
    google_groups,
    google_group_members,
    google_users,
    google_groups_w_users,
):
    mock_service = MagicMock()
    groups = google_groups(2, prefix="test-")
    groups_to_filter_out = google_groups(4)[2:]
    groups.extend(groups_to_filter_out)
    group_members = [[], google_group_members(2)]
    users = google_users(2)
    groups_with_users = google_groups_w_users(4, 2, group_prefix="test-")[:2]
    groups_with_users.remove(groups_with_users[0])

    mock_list_groups.return_value = groups
    mock_list_group_members.side_effect = group_members
    mock_list_users.return_value = users
    mock_filter_by_condition.return_value = groups[:2]

    groups_filters = [lambda group: "test-" in group["name"]]

    assert (
        directory.list_groups_with_members(mock_service, groups_filters=groups_filters)
        == groups_with_users
    )
    assert mock_filter_by_condition.called_once_with(groups, groups_filters)
    assert mock_list_group_members.call_count == 2
    assert mock_list_users.call_count == 1


@patch("integrations.google_next.directory.logger")
@patch("integrations.google_next.directory.get_members_details")
@patch("integrations.google_next.directory.retry_request")
@patch("integrations.google_next.directory.list_groups")
@patch("integrations.google_next.directory.list_group_members")
@patch("integrations.google_next.directory.list_users")
def test_list_groups_with_members_updates_group_with_group_error(
    mock_list_users: MagicMock,
    mock_list_group_members: MagicMock,
    mock_list_groups: MagicMock,
    mock_retry_request: MagicMock,
    mock_get_members_details: MagicMock,
    mock_logger: MagicMock,
):
    """Test list_groups_with_members returns groups with members."""

    mock_service = MagicMock()

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
            "error": "Error getting members: Exception",
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

    mock_list_groups.return_value = groups
    mock_list_group_members.side_effect = group_members
    mock_list_users.side_effect = users
    mock_retry_request.side_effect = [Exception("Exception"), group_members[1]]
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
        assert directory.list_groups_with_members(mock_service) == expected_output

    mock_logger.info.assert_has_calls(
        [
            call("Found 2 groups."),
            call("Found 2 groups after filtering."),
            call("Getting members for group: group_email1"),
            call("Getting members for group: group_email2"),
        ]
    )
    mock_logger.warning.assert_called_once_with(
        "Error getting members for group group_email1: Exception"
    )
    mock_logger.error.assert_not_called()


@patch("integrations.google_next.directory.logger")
@patch("integrations.google_next.directory.get_members_details")
@patch("integrations.google_next.directory.retry_request")
@patch("integrations.google_next.directory.list_groups")
@patch("integrations.google_next.directory.list_group_members")
@patch("integrations.google_next.directory.list_users")
def test_list_groups_with_members_updates_group_with_user_details_error(
    mock_list_users: MagicMock,
    mock_list_group_members: MagicMock,
    mock_list_groups: MagicMock,
    mock_retry_request: MagicMock,
    mock_get_members_details: MagicMock,
    mock_logger: MagicMock,
):
    """Test list_groups_with_members returns groups with members."""

    mock_service = MagicMock()

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

    mock_list_groups.return_value = groups
    mock_list_users.side_effect = users
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

    assert directory.list_groups_with_members(mock_service) == expected_output

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


def test_get_members_details_returns_members():
    """Test get_members_details returns members."""
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

    assert directory.get_members_details(members, users) == expected_result


@patch("integrations.google_next.directory.logger")
def test_get_members_details_returns_members_with_error(
    mock_logger: MagicMock,
):
    """Test get_members_details returns members."""
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

    assert directory.get_members_details(members, users) == expected_result

    mock_logger.info.assert_has_calls(
        [
            call("Getting user details for member: email1"),
            call("Getting user details for member: email2"),
        ]
    )
    mock_logger.warning.assert_called_once_with(
        "User details not found for member: email1"
    )
