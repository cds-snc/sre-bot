from unittest.mock import patch
from integrations.aws import sso_admin


@patch("integrations.aws.sso_admin.SYSTEM_ADMIN_PERMISSIONS", "test_admin_permissions")
@patch("integrations.aws.sso_admin.VIEW_ONLY_PERMISSIONS", "test_view_permissions")
def test_get_predefined_permission_sets():
    assert sso_admin.get_predefined_permission_sets("write") == "test_admin_permissions"
    assert sso_admin.get_predefined_permission_sets("read") == "test_view_permissions"
    assert sso_admin.get_predefined_permission_sets("other") == "other"
    assert sso_admin.get_predefined_permission_sets(None) is None


@patch("integrations.aws.sso_admin.execute_aws_api_call")
@patch("integrations.aws.sso_admin.get_predefined_permission_sets")
def test_create_assignment_for_user_returns_true_if_permissions_added_with_write(
    mock_get_predefined_permission_sets, mock_execute_aws_api_call
):

    mock_get_predefined_permission_sets.return_value = "test_admin_permissions"
    mock_execute_aws_api_call.return_value = {
        "AccountAssignmentCreationStatus": {"Status": "SUCCESS"}
    }

    assert (
        sso_admin.create_account_assignment("test_user", "test_account", "write")
        is True
    )


@patch("integrations.aws.sso_admin.execute_aws_api_call")
@patch("integrations.aws.sso_admin.get_predefined_permission_sets")
def test_create_assignment_for_user_returns_true_if_permissions_added_with_read(
    mock_get_predefined_permission_sets, mock_execute_aws_api_call
):

    mock_get_predefined_permission_sets.return_value = "test_view_permissions"
    mock_execute_aws_api_call.return_value = {
        "AccountAssignmentCreationStatus": {"Status": "SUCCESS"}
    }

    assert (
        sso_admin.create_account_assignment("test_user", "test_account", "read") is True
    )


@patch("integrations.aws.sso_admin.execute_aws_api_call")
@patch("integrations.aws.sso_admin.get_predefined_permission_sets")
def test_create_assignment_for_user_returns_false_if_permissions_failed(
    mock_get_predefined_permission_sets, mock_execute_aws_api_call
):

    mock_get_predefined_permission_sets.return_value = "test_view_permissions"
    mock_execute_aws_api_call.return_value = {
        "AccountAssignmentCreationStatus": {"Status": "FAILED"}
    }

    assert (
        sso_admin.create_account_assignment("test_user", "test_account", "read")
        is False
    )


@patch("integrations.aws.sso_admin.execute_aws_api_call")
@patch("integrations.aws.sso_admin.get_predefined_permission_sets")
def test_delete_assignment_for_user_returns_true_if_permissions_added_with_write(
    mock_get_predefined_permission_sets, mock_execute_aws_api_call
):

    mock_get_predefined_permission_sets.return_value = "test_admin_permissions"
    mock_execute_aws_api_call.return_value = {
        "AccountAssignmentDeletionStatus": {"Status": "SUCCESS"}
    }

    assert (
        sso_admin.delete_account_assignment("test_user", "test_account", "write")
        is True
    )


@patch("integrations.aws.sso_admin.execute_aws_api_call")
@patch("integrations.aws.sso_admin.get_predefined_permission_sets")
def test_delete_assignment_for_user_returns_true_if_permissions_added_with_read(
    mock_get_predefined_permission_sets, mock_execute_aws_api_call
):

    mock_get_predefined_permission_sets.return_value = "test_view_permissions"
    mock_execute_aws_api_call.return_value = {
        "AccountAssignmentDeletionStatus": {"Status": "SUCCESS"}
    }

    assert (
        sso_admin.delete_account_assignment("test_user", "test_account", "read") is True
    )


@patch("integrations.aws.sso_admin.execute_aws_api_call")
@patch("integrations.aws.sso_admin.get_predefined_permission_sets")
def test_delete_assignment_for_user_returns_false_if_permissions_failed(
    mock_get_predefined_permission_sets, mock_execute_aws_api_call
):

    mock_get_predefined_permission_sets.return_value = "test_view_permissions"
    mock_execute_aws_api_call.return_value = {
        "AccountAssignmentDeletionStatus": {"Status": "FAILED"}
    }

    assert (
        sso_admin.delete_account_assignment("test_user", "test_account", "read")
        is False
    )
