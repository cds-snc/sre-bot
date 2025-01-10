""""Unit tests for the Google Directory API."""

from unittest.mock import MagicMock, patch

import pytest
from integrations.google_next import directory

GOOGLE_WORKSPACE_CUSTOMER_ID = "test_customer_id"


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
    print("DEBUG: groups_with_users", groups_with_users)
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
def test_list_groups_with_members_update_group_with_error(
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
        {"id": "test_group_id1", "name": "test_group1", "email": "email1"},
        {"id": "test_group_id2", "name": "test_group2", "email": "email2"},
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
            "email": "email1",
            "error": "Error getting members: Exception",
        },
        {
            "id": "test_group_id2",
            "name": "test_group2",
            "email": "email2",
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
        Exception("Exception"),
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

    mock_logger.warning.assert_called_once_with(
        "Error getting members for group email1: Exception"
    )


# @patch("integrations.google_next.directory.retry_request")
# @patch("integrations.google_next.directory.list_users")
# def test_get_members_details_returns_members(
#     mock_list_users: MagicMock, mock_retry_request: MagicMock
# ):
#     """Test get_members_details returns members."""
#     mock_service = MagicMock()
#     members = [
#         {"email": "email1", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
#         {"email": "email2", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
#     ]

#     users = [
#         {"name": "user1", "primaryEmail": "email1"},
#         {"name": "user2", "primaryEmail": "email2"},
#     ]

#     mock_retry_request.side_effect = [users[0], users[1]]

#     expected_result = [
#         {
#             "email": "email1",
#             "role": "MEMBER",
#             "type": "USER",
#             "status": "ACTIVE",
#             "name": "user1",
#             "primaryEmail": "email1",
#         },
#         {
#             "email": "email2",
#             "role": "MEMBER",
#             "type": "USER",
#             "status": "ACTIVE",
#             "name": "user2",
#             "primaryEmail": "email2",
#         },
#     ]

#     assert directory.get_members_details(mock_service, members) == expected_result


# @patch("integrations.google_next.directory.retry_request")
# @patch("integrations.google_next.directory.list_users")
# def test_get_members_details_returns_members_with_error(
#     mock_get_user: MagicMock, mock_retry_request: MagicMock
# ):
#     """Test get_members_details returns members."""
#     mock_service = MagicMock()
#     members = [
#         {"email": "email1", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
#         {"email": "email2", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
#     ]

#     users = [
#         Exception("Error fetching user details"),
#         {"name": "user2", "primaryEmail": "email2"},
#     ]

#     mock_retry_request.side_effect = [users[0], users[1]]

#     expected_result = [
#         {
#             "email": "email1",
#             "role": "MEMBER",
#             "type": "USER",
#             "status": "ACTIVE",
#             "error": "Error fetching user details",
#         },
#         {
#             "email": "email2",
#             "role": "MEMBER",
#             "type": "USER",
#             "status": "ACTIVE",
#             "name": "user2",
#             "primaryEmail": "email2",
#         },
#     ]

#     assert directory.get_members_details(mock_service, members) == expected_result
