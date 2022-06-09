from integrations import aws_sso

from unittest.mock import call, MagicMock, patch


@patch("integrations.aws_sso.assume_role_client")
def test_add_permissions_for_user_returns_true_if_permissions_added_with_write(
    assume_role_client_mock,
):
    client = MagicMock()
    client.create_account_assignment.return_value = {
        "AccountAssignmentCreationStatus": {"Status": "SUCCESS"}
    }
    assume_role_client_mock.return_value = client
    assert (
        aws_sso.add_permissions_for_user("test_user", "test_account", "write") is True
    )


@patch("integrations.aws_sso.assume_role_client")
def test_add_permissions_for_user_returns_true_if_permissions_added_with_read(
    assume_role_client_mock,
):
    client = MagicMock()
    client.create_account_assignment.return_value = {
        "AccountAssignmentCreationStatus": {"Status": "SUCCESS"}
    }
    assume_role_client_mock.return_value = client
    assert aws_sso.add_permissions_for_user("test_user", "test_account", "read") is True


@patch("integrations.aws_sso.assume_role_client")
def test_add_permissions_for_user_returns_false_if_permissions_failed(
    assume_role_client_mock,
):
    client = MagicMock()
    client.create_account_assignment.return_value = {
        "AccountAssignmentCreationStatus": {"Status": "FAILED"}
    }
    assume_role_client_mock.return_value = client
    assert (
        aws_sso.add_permissions_for_user("test_user", "test_account", "read") is False
    )


@patch("integrations.aws_sso.boto3")
def test_assume_role_client_returns_session(boto3_mock):
    client = MagicMock()
    client.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "test_access_key_id",
            "SecretAccessKey": "test_secret_access_key",
            "SessionToken": "test_session_token",
        }
    }
    session = MagicMock()
    session.client.return_value = "session-client"
    boto3_mock.client.return_value = client
    boto3_mock.Session.return_value = session
    assert aws_sso.assume_role_client("identitystore") == "session-client"
    assert boto3_mock.client.call_count == 1
    assert boto3_mock.Session.call_count == 1
    assert boto3_mock.Session.call_args == call(
        aws_access_key_id="test_access_key_id",
        aws_secret_access_key="test_secret_access_key",
        aws_session_token="test_session_token",
    )


@patch("integrations.aws_sso.ACCOUNTS", {"id": "name"})
def test_get_accounts():
    assert aws_sso.get_accounts() == {"id": "name"}


@patch("integrations.aws_sso.assume_role_client")
def test_get_accounts_for_permission_set_returns_empty_list_if_no_accounts_found(
    assume_role_client_mock,
):
    client = MagicMock()
    client.list_accounts_for_provisioned_permission_set.return_value = {
        "AccountIds": [],
    }
    assume_role_client_mock.return_value = client
    assert aws_sso.get_accounts_for_permission_set("test_permission_set") == []


@patch("integrations.aws_sso.assume_role_client")
def test_get_user_id_returns_users_if_they_exist(assume_role_client_mock):
    client = MagicMock()
    client.list_users.return_value = {"Users": [{"UserId": "test_user_id"}]}
    assume_role_client_mock.return_value = client
    assert aws_sso.get_user_id("test_user") == "test_user_id"


@patch("integrations.aws_sso.assume_role_client")
def test_get_user_id_returns_none_if_they_do_not_exist(assume_role_client_mock):
    client = MagicMock()
    client.list_users.return_value = {"Users": []}
    assume_role_client_mock.return_value = client
    assert aws_sso.get_user_id("test_user") is None


@patch("integrations.aws_sso.assume_role_client")
def test_remove_permissions_for_user_returns_true_if_permissions_added_with_write(
    assume_role_client_mock,
):
    client = MagicMock()
    client.delete_account_assignment.return_value = {
        "AccountAssignmentDeletionStatus": {"Status": "SUCCESS"}
    }
    assume_role_client_mock.return_value = client
    assert (
        aws_sso.remove_permissions_for_user("test_user", "test_account", "write")
        is True
    )


@patch("integrations.aws_sso.assume_role_client")
def test_remove_permissions_for_user_returns_true_if_permissions_added_with_read(
    assume_role_client_mock,
):
    client = MagicMock()
    client.delete_account_assignment.return_value = {
        "AccountAssignmentDeletionStatus": {"Status": "SUCCESS"}
    }
    assume_role_client_mock.return_value = client
    assert (
        aws_sso.remove_permissions_for_user("test_user", "test_account", "read") is True
    )


@patch("integrations.aws_sso.assume_role_client")
def test_remove_permissions_for_user_returns_false_if_permissions_failed(
    assume_role_client_mock,
):
    client = MagicMock()
    client.delete_account_assignment.return_value = {
        "AccountAssignmentDeletionStatus": {"Status": "FAILED"}
    }
    assume_role_client_mock.return_value = client
    assert (
        aws_sso.remove_permissions_for_user("test_user", "test_account", "read")
        is False
    )
