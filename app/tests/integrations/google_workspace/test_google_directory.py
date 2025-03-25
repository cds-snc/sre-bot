"""Unit tests for google_directory module."""

from unittest.mock import patch

import pandas as pd
from integrations.google_workspace import google_directory


@patch(
    "integrations.google_workspace.google_directory.GOOGLE_DELEGATED_ADMIN_EMAIL",
    new="default_delegated_admin_email",
)
@patch(
    "integrations.google_workspace.google_directory.google_service.execute_google_api_call"
)
def test_get_user_returns_user(execute_google_api_call_mock):
    execute_google_api_call_mock.return_value = {
        "id": "test_user_id",
        "name": "test_user",
        "email": "user.name@domain.com",
    }

    assert google_directory.get_user("test_user_id") == {
        "id": "test_user_id",
        "name": "test_user",
        "email": "user.name@domain.com",
    }

    execute_google_api_call_mock.assert_called_once_with(
        "admin",
        "directory_v1",
        "users",
        "get",
        ["https://www.googleapis.com/auth/admin.directory.user.readonly"],
        "default_delegated_admin_email",
        userKey="test_user_id",
        fields=None,
    )


@patch(
    "integrations.google_workspace.google_directory.google_service.execute_google_api_call"
)
def test_get_user_uses_custom_delegated_user_email_if_provided(
    execute_google_api_call_mock,
):
    execute_google_api_call_mock.return_value = {
        "id": "test_user_id",
        "name": "test_user",
        "email": "user.name@domain.com",
    }

    custom_delegated_user_email = "custom.email@domain.com"
    assert google_directory.get_user("test_user_id", custom_delegated_user_email) == {
        "id": "test_user_id",
        "name": "test_user",
        "email": "user.name@domain.com",
    }

    execute_google_api_call_mock.assert_called_once_with(
        "admin",
        "directory_v1",
        "users",
        "get",
        ["https://www.googleapis.com/auth/admin.directory.user.readonly"],
        "custom.email@domain.com",
        userKey="test_user_id",
        fields=None,
    )


@patch(
    "integrations.google_workspace.google_directory.GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="default_google_workspace_customer_id",
)
@patch(
    "integrations.google_workspace.google_directory.GOOGLE_DELEGATED_ADMIN_EMAIL",
    new="default_delegated_admin_email",
)
@patch(
    "integrations.google_workspace.google_directory.google_service.execute_google_api_call"
)
def test_list_users_returns_users(execute_google_api_call_mock):
    # Mock the results
    results = [
        {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
    ]

    execute_google_api_call_mock.return_value = results

    assert google_directory.list_users() == results

    execute_google_api_call_mock.assert_called_once_with(
        "admin",
        "directory_v1",
        "users",
        "list",
        ["https://www.googleapis.com/auth/admin.directory.user.readonly"],
        "default_delegated_admin_email",
        paginate=True,
        customer="default_google_workspace_customer_id",
        maxResults=500,
        orderBy="email",
    )


@patch(
    "integrations.google_workspace.google_directory.google_service.execute_google_api_call"
)
def test_list_users_uses_custom_delegated_user_email_and_customer_id_if_provided(
    execute_google_api_call_mock,
):
    # Mock the results
    results = [
        {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
    ]

    execute_google_api_call_mock.return_value = results

    custom_delegated_user_email = "custom.email@domain.com"
    custom_customer_id = "custom_customer_id"

    assert (
        google_directory.list_users(custom_delegated_user_email, custom_customer_id)
        == results
    )

    execute_google_api_call_mock.assert_called_once_with(
        "admin",
        "directory_v1",
        "users",
        "list",
        ["https://www.googleapis.com/auth/admin.directory.user.readonly"],
        custom_delegated_user_email,
        paginate=True,
        customer=custom_customer_id,
        maxResults=500,
        orderBy="email",
    )


@patch(
    "integrations.google_workspace.google_directory.GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="default_google_workspace_customer_id",
)
@patch(
    "integrations.google_workspace.google_directory.GOOGLE_DELEGATED_ADMIN_EMAIL",
    new="default_delegated_admin_email",
)
@patch(
    "integrations.google_workspace.google_directory.google_service.execute_google_api_call"
)
def test_list_groups_calls_execute_google_api_call(
    mock_execute_google_api_call,
):
    google_directory.list_groups()
    mock_execute_google_api_call.assert_called_once_with(
        "admin",
        "directory_v1",
        "groups",
        "list",
        ["https://www.googleapis.com/auth/admin.directory.group.readonly"],
        "default_delegated_admin_email",
        paginate=True,
        customer="default_google_workspace_customer_id",
        maxResults=200,
        orderBy="email",
    )


@patch(
    "integrations.google_workspace.google_directory.GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="default_google_workspace_customer_id",
)
@patch(
    "integrations.google_workspace.google_directory.GOOGLE_DELEGATED_ADMIN_EMAIL",
    new="default_delegated_admin_email",
)
@patch("integrations.google_workspace.google_directory.convert_string_to_camel_case")
@patch(
    "integrations.google_workspace.google_directory.google_service.execute_google_api_call"
)
def test_list_groups_calls_execute_google_api_call_with_kwargs(
    mock_execute_google_api_call, mock_convert_string_to_camel_case
):
    mock_convert_string_to_camel_case.return_value = "customArgument"
    google_directory.list_groups(custom_argument="test_customer_id")
    mock_execute_google_api_call.assert_called_once_with(
        "admin",
        "directory_v1",
        "groups",
        "list",
        ["https://www.googleapis.com/auth/admin.directory.group.readonly"],
        "default_delegated_admin_email",
        paginate=True,
        customer="default_google_workspace_customer_id",
        maxResults=200,
        orderBy="email",
        customArgument="test_customer_id",
    )
    assert mock_convert_string_to_camel_case.called_once


@patch(
    "integrations.google_workspace.google_directory.google_service.execute_google_api_call"
)
def test_list_groups_uses_custom_delegated_user_email_and_customer_id_if_provided(
    execute_google_api_call_mock,
):
    # Mock the results
    results = [
        {"id": "test_group_id", "name": "test_group", "email": "email@domain.com"},
        {"id": "test_group_id2", "name": "test_group2", "email": "email2@domain.com"},
    ]

    execute_google_api_call_mock.return_value = results

    custom_delegated_user_email = "custom.email@domain.com"
    custom_customer_id = "custom_customer_id"

    assert (
        google_directory.list_groups(custom_delegated_user_email, custom_customer_id)
        == results
    )

    execute_google_api_call_mock.assert_called_once_with(
        "admin",
        "directory_v1",
        "groups",
        "list",
        ["https://www.googleapis.com/auth/admin.directory.group.readonly"],
        custom_delegated_user_email,
        paginate=True,
        customer=custom_customer_id,
        maxResults=200,
        orderBy="email",
    )


@patch(
    "integrations.google_workspace.google_directory.GOOGLE_DELEGATED_ADMIN_EMAIL",
    new="default_delegated_admin_email",
)
@patch(
    "integrations.google_workspace.google_directory.google_service.execute_google_api_call"
)
def test_list_group_members_calls_execute_google_api_call_with_correct_args(
    mock_execute_google_api_call,
):
    group_key = "test_group_key"
    google_directory.list_group_members(group_key)
    mock_execute_google_api_call.assert_called_once_with(
        "admin",
        "directory_v1",
        "members",
        "list",
        ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"],
        "default_delegated_admin_email",
        paginate=True,
        groupKey=group_key,
        maxResults=200,
        fields=None,
    )


@patch(
    "integrations.google_workspace.google_directory.google_service.execute_google_api_call"
)
def test_list_group_members_uses_custom_delegated_user_email_if_provided(
    execute_google_api_call_mock,
):
    # Mock the results
    results = [
        {"id": "test_member_id", "email": "member@domain.com"},
        {"id": "test_member_id2", "email": "member2@domain.com"},
    ]

    execute_google_api_call_mock.return_value = results

    group_key = "test_group_key"
    custom_delegated_user_email = "custom.email@domain.com"

    assert (
        google_directory.list_group_members(group_key, custom_delegated_user_email)
        == results
    )

    execute_google_api_call_mock.assert_called_once_with(
        "admin",
        "directory_v1",
        "members",
        "list",
        ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"],
        custom_delegated_user_email,
        paginate=True,
        groupKey=group_key,
        maxResults=200,
        fields=None,
    )


@patch(
    "integrations.google_workspace.google_directory.GOOGLE_DELEGATED_ADMIN_EMAIL",
    "default_delegated_admin_email",
)
@patch(
    "integrations.google_workspace.google_directory.google_service.execute_google_api_call"
)
def test_get_group_calls_execute_google_api_call_with_correct_args(
    mock_execute_google_api_call,
):
    group_key = "test_group_key"
    google_directory.get_group(group_key)
    mock_execute_google_api_call.assert_called_once_with(
        "admin",
        "directory_v1",
        "groups",
        "get",
        ["https://www.googleapis.com/auth/admin.directory.group.readonly"],
        "default_delegated_admin_email",
        groupKey=group_key,
        fields=None,
    )


@patch("integrations.google_workspace.google_directory.list_group_members")
def test_add_users_to_group_calls_list_group_members(mock_list_group_members):
    group = {"id": "test_group_id"}
    group_key = "test_group_id"
    google_directory.add_users_to_group(group, group_key)
    mock_list_group_members.assert_called_once_with(group_key)


@patch("integrations.google_workspace.google_directory.list_group_members")
def test_add_users_to_group_adds_members(mock_list_group_members):
    mock_list_group_members.return_value = [{"id": "test_member_id"}]
    group = {"id": "test_group_id"}
    group_key = "test_group_id"
    google_directory.add_users_to_group(group, group_key)
    assert group["members"] == [{"id": "test_member_id"}]


@patch("integrations.google_workspace.google_directory.list_group_members")
def test_add_users_to_group_skips_when_no_members(mock_list_group_members):
    mock_list_group_members.return_value = []
    group = {"id": "test_group_id"}
    group_key = "test_group_id"
    google_directory.add_users_to_group(group, group_key)
    assert group.get("members") is None


@patch("integrations.google_workspace.google_directory.list_groups")
@patch("integrations.google_workspace.google_directory.list_group_members")
@patch("integrations.google_workspace.google_directory.list_users")
def test_list_groups_with_members(
    mock_list_users,
    mock_list_group_members,
    mock_list_groups,
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

    mock_list_groups.return_value = groups
    mock_list_group_members.side_effect = group_members
    mock_list_users.return_value = users

    assert google_directory.list_groups_with_members() == groups_with_users


@patch("integrations.google_workspace.google_directory.filters.filter_by_condition")
@patch("integrations.google_workspace.google_directory.list_groups")
@patch("integrations.google_workspace.google_directory.list_group_members")
@patch("integrations.google_workspace.google_directory.list_users")
def test_list_groups_with_members_filtered(
    mock_list_users,
    mock_list_group_members,
    mock_list_groups,
    mock_filter_by_condition,
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

    mock_list_groups.return_value = groups
    mock_list_group_members.side_effect = group_members
    mock_list_users.return_value = users
    mock_filter_by_condition.return_value = groups[:2]
    groups_filters = [lambda group: "test-" in group["name"]]

    assert (
        google_directory.list_groups_with_members(groups_filters=groups_filters)
        == groups_with_users
    )
    assert mock_filter_by_condition.called_once_with(groups, groups_filters)
    assert mock_list_group_members.call_count == 2
    assert mock_list_users.call_count == 1


@patch("integrations.google_workspace.google_directory.list_users")
@patch("integrations.google_workspace.google_directory.retry_request")
@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members_error_in_list_group_members(
    mock_list_groups,
    mock_retry_request,
    mock_list_users,
    google_groups,
    google_group_members,
    google_users,
    google_groups_w_users,
):
    groups = google_groups(2)
    group_members = [Exception("Error fetching group members"), google_group_members(2)]
    users = google_users(2)

    mock_list_groups.return_value = groups
    mock_retry_request.side_effect = [
        group_members[0],
        group_members[1],
        users[0],
        users[1],
    ]
    mock_list_users.return_value = users

    # Only the second group should be processed
    expected_groups_with_users = [groups[1]]
    expected_groups_with_users[0]["members"] = group_members[1]
    expected_groups_with_users[0]["members"][0].update(users[0])
    expected_groups_with_users[0]["members"][1].update(users[1])

    assert google_directory.list_groups_with_members() == expected_groups_with_users


@patch("integrations.google_workspace.google_directory.list_users")
@patch("integrations.google_workspace.google_directory.get_members_details")
@patch("integrations.google_workspace.google_directory.retry_request")
@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members_error_in_get_user(
    mock_list_groups,
    mock_retry_request,
    mock_get_members_details,
    mock_list_users,
    google_groups,
    google_group_members,
    google_users,
):
    groups = google_groups(2)
    group_members = [google_group_members(2), google_group_members(2)]
    users = [
        Exception("Error fetching user details"),
        google_users(2)[1],
        google_users(1)[0],
        google_users(2)[1],
    ]

    mock_list_groups.return_value = groups
    mock_retry_request.side_effect = [
        group_members[0],
        group_members[1],
    ]
    mock_get_members_details.side_effect = [
        [],
        group_members[1],
    ]
    mock_list_users.return_value = users

    # Only the second group should be processed
    expected_groups_with_users = [groups[1]]
    expected_groups_with_users[0]["members"] = group_members[1]
    expected_groups_with_users[0]["members"][0].update(users[2])
    expected_groups_with_users[0]["members"][1].update(users[3])

    assert google_directory.list_groups_with_members() == expected_groups_with_users


@patch("integrations.google_workspace.google_directory.list_users")
@patch("integrations.google_workspace.google_directory.retry_request")
@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members_tolerate_errors(
    mock_list_groups,
    mock_retry_request,
    mock_list_users,
    google_groups_w_users,
):

    groups = [
        {
            "id": "group1",
            "email": "groupEmail1",
            "name": "name1",
            "directMembersCount": 2,
        },
        {
            "id": "group2",
            "email": "groupEmail2",
            "name": "name2",
            "directMembersCount": 2,
        },
    ]

    group_members = [
        [
            {"email": "email1", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
            {"email": "email2", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
        ],
        [
            {"email": "email3", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
            {"email": "email4", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
        ],
    ]

    users = [
        # Exception("Error fetching user details"),
        {"id": "user2", "name": "user2", "primaryEmail": "email2"},
        {"id": "user3", "name": "user3", "primaryEmail": "email3"},
        {"id": "user4", "name": "user4", "primaryEmail": "email4"},
    ]

    mock_list_groups.return_value = groups
    mock_retry_request.side_effect = [
        group_members[0],
        group_members[1],
    ]

    mock_list_users.return_value = users

    # Expected result should include both groups, with the second group having one member
    expected_groups_with_users = [
        {
            "id": "group1",
            "email": "groupEmail1",
            "name": "name1",
            "directMembersCount": 2,
            "members": [
                {
                    "email": "email1",
                    "role": "MEMBER",
                    "type": "USER",
                    "status": "ACTIVE",
                },
                {
                    "email": "email2",
                    "primaryEmail": "email2",
                    "role": "MEMBER",
                    "type": "USER",
                    "status": "ACTIVE",
                    "id": "user2",
                    "name": "user2",
                },
            ],
        },
        {
            "id": "group2",
            "email": "groupEmail2",
            "name": "name2",
            "directMembersCount": 2,
            "members": [
                {
                    "email": "email3",
                    "primaryEmail": "email3",
                    "role": "MEMBER",
                    "type": "USER",
                    "status": "ACTIVE",
                    "id": "user3",
                    "name": "user3",
                },
                {
                    "email": "email4",
                    "primaryEmail": "email4",
                    "role": "MEMBER",
                    "type": "USER",
                    "status": "ACTIVE",
                    "id": "user4",
                    "name": "user4",
                },
            ],
        },
    ]

    result = google_directory.list_groups_with_members(tolerate_errors=True)

    assert result == expected_groups_with_users


@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members_skips_when_no_groups(mock_list_groups):
    mock_list_groups.return_value = []
    assert google_directory.list_groups_with_members() == []


@patch("integrations.google_workspace.google_directory.filters.filter_by_condition")
@patch("integrations.google_workspace.google_directory.list_groups")
@patch("integrations.google_workspace.google_directory.list_group_members")
@patch("integrations.google_workspace.google_directory.list_users")
def test_list_groups_with_members_filtered_dataframe(
    mock_list_users,
    mock_list_group_members,
    mock_list_groups,
    mock_filter_by_condition,
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

    mock_list_groups.return_value = groups
    mock_list_group_members.side_effect = group_members
    mock_list_users.return_value = users
    mock_filter_by_condition.return_value = groups[:2]
    groups_filters = [lambda group: "test-" in group["name"]]

    groups_result = google_directory.list_groups_with_members(
        groups_filters=groups_filters
    )
    result = google_directory.convert_google_groups_members_to_dataframe(groups_result)

    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert set(result.columns) == {
        "group_email",
        "group_name",
        "group_direct_members_count",
        "group_description",
        "member_email",
        "member_role",
        "member_type",
        "member_status",
        "member_primary_email",
        "member_given_name",
        "member_family_name",
    }


def test_get_members_details_breaks_on_error():
    members = [
        {"email": "email1", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
        {"email": "email2", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
    ]

    users = [
        {"name": "user2", "primaryEmail": "email2"},
    ]

    result = google_directory.get_members_details(members, users)

    assert result == []


def test_get_members_details_continues_on_tolerate_errors():
    members = [
        {"email": "email1", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
        {"email": "email2", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
    ]

    users = [
        {"name": "user2", "primaryEmail": "email2"},
    ]

    result = google_directory.get_members_details(members, users, tolerate_errors=True)

    expected_result = [
        members[0],
        {
            "email": "email2",
            "role": "MEMBER",
            "type": "USER",
            "status": "ACTIVE",
            "name": "user2",
            "primaryEmail": "email2",
        },
    ]
    assert result == expected_result
