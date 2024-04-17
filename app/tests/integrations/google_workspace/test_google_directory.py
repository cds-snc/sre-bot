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
        maxResults=10,
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
def test_list_groups_calls_execute_google_api_call_with_correct_args(
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
        maxResults=100,
        orderBy="email",
    )


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
        maxResults=100,
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
    )
