"""Unit tests for google_directory module."""
from unittest.mock import patch
from integrations.google_workspace import google_directory


@patch(
    "integrations.google_workspace.google_directory.DEFAULT_DELEGATED_ADMIN_EMAIL",
    new="default_delegated_admin_email",
)
@patch("integrations.google_workspace.google_directory.execute_google_api_call")
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
    )


@patch("integrations.google_workspace.google_directory.execute_google_api_call")
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
    )


@patch(
    "integrations.google_workspace.google_directory.DEFAULT_GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="default_google_workspace_customer_id",
)
@patch(
    "integrations.google_workspace.google_directory.DEFAULT_DELEGATED_ADMIN_EMAIL",
    new="default_delegated_admin_email",
)
@patch("integrations.google_workspace.google_directory.execute_google_api_call")
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


@patch("integrations.google_workspace.google_directory.execute_google_api_call")
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
    "integrations.google_workspace.google_directory.DEFAULT_GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="default_google_workspace_customer_id",
)
@patch(
    "integrations.google_workspace.google_directory.DEFAULT_DELEGATED_ADMIN_EMAIL",
    new="default_delegated_admin_email",
)
@patch("integrations.google_workspace.google_directory.execute_google_api_call")
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
    "integrations.google_workspace.google_directory.DEFAULT_GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="default_google_workspace_customer_id",
)
@patch(
    "integrations.google_workspace.google_directory.DEFAULT_DELEGATED_ADMIN_EMAIL",
    new="default_delegated_admin_email",
)
@patch("integrations.google_workspace.google_directory.convert_string_to_camel_case")
@patch("integrations.google_workspace.google_directory.execute_google_api_call")
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


@patch("integrations.google_workspace.google_directory.execute_google_api_call")
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
    "integrations.google_workspace.google_directory.DEFAULT_DELEGATED_ADMIN_EMAIL",
    new="default_delegated_admin_email",
)
@patch("integrations.google_workspace.google_directory.execute_google_api_call")
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
    )


@patch("integrations.google_workspace.google_directory.execute_google_api_call")
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
@patch("integrations.google_workspace.google_directory.get_user")
def test_list_groups_with_members(
    mock_get_user,
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
    mock_get_user.side_effect = users

    assert google_directory.list_groups_with_members() == groups_with_users


@patch("integrations.google_workspace.google_directory.filters.filter_by_condition")
@patch("integrations.google_workspace.google_directory.list_groups")
@patch("integrations.google_workspace.google_directory.list_group_members")
@patch("integrations.google_workspace.google_directory.get_user")
def test_list_groups_with_members_filtered(
    mock_get_user,
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
    mock_get_user.side_effect = users
    mock_filter_by_condition.return_value = groups[:2]
    filters = [lambda group: "test-" in group["name"]]

    assert (
        google_directory.list_groups_with_members(filters=filters) == groups_with_users
    )
    assert mock_filter_by_condition.called_once_with(groups, filters)
    assert mock_list_group_members.call_count == 2
    assert mock_get_user.call_count == 2


@patch("integrations.google_workspace.google_directory.list_groups")
@patch("integrations.google_workspace.google_directory.list_group_members")
@patch("integrations.google_workspace.google_directory.get_user")
def test_list_groups_with_members_without_details(
    mock_get_user,
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

    groups_with_users[0].pop("members", None)
    groups_with_users[1].pop("members", None)

    mock_list_groups.return_value = groups
    mock_list_group_members.side_effect = group_members
    mock_get_user.side_effect = users

    assert google_directory.list_groups_with_members(members_details=False) == []


@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members_skips_when_no_groups(mock_list_groups):
    mock_list_groups.return_value = []
    assert google_directory.list_groups_with_members() == []
