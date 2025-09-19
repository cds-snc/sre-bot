import json
from unittest.mock import patch, MagicMock
from modules.aws import ops_group_assignment


@patch("modules.aws.ops_group_assignment.AWS_OPS_GROUP_NAME", "OpsGroup")
@patch("modules.aws.ops_group_assignment.logger")
@patch("modules.aws.ops_group_assignment.sso_admin")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.identity_store")
def test_execute_assigns_to_unassigned_accounts(
    mock_identity_store, mock_organizations, mock_sso_admin, mock_logger
):
    mock_identity_store.get_group_id.return_value = "group-id"
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Status": "ACTIVE"},
        {"Id": "222222222222", "Status": "SUSPENDED"},
        {"Id": "333333333333", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = [
        {
            "AccountId": "111111111111",
            "PrincipalId": "group-id",
            "PrincipalType": "GROUP",
        }
    ]
    mock_sso_admin.create_account_assignment.return_value = True
    result = ops_group_assignment.execute()
    assert result["status"] == "success"
    assert "assigned to account" in result["message"]


@patch("modules.aws.ops_group_assignment.AWS_OPS_GROUP_NAME", None)
def test_execute_feature_disabled():
    result = ops_group_assignment.execute()
    assert result is None


@patch("modules.aws.ops_group_assignment.AWS_OPS_GROUP_NAME", "OpsGroup")
@patch("modules.aws.ops_group_assignment.logger")
@patch("modules.aws.ops_group_assignment.sso_admin")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.identity_store")
def test_execute_ops_group_not_found(
    mock_identity_store, mock_organizations, mock_sso_admin, mock_logger
):
    mock_identity_store.get_group_id.return_value = None
    result = ops_group_assignment.execute()
    assert result["status"] == "failed"
    assert "not found" in result["message"]


@patch("modules.aws.ops_group_assignment.AWS_OPS_GROUP_NAME", "OpsGroup")
@patch("modules.aws.ops_group_assignment.logger")
@patch("modules.aws.ops_group_assignment.sso_admin")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.identity_store")
def test_execute_account_missing_id(
    mock_identity_store, mock_organizations, mock_sso_admin, mock_logger
):
    mock_identity_store.get_group_id.return_value = "group-id"
    mock_organizations.list_organization_accounts.return_value = [
        {"Name": "NoIdAccount", "Status": "ACTIVE"},
        {"Id": "111111111111", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = []
    mock_sso_admin.create_account_assignment.return_value = True
    result = ops_group_assignment.execute()
    assert result["status"] == "success"
    mock_logger.error.assert_any_call(
        "account_missing_id",
        account=json.dumps({"Name": "NoIdAccount", "Status": "ACTIVE"}, default=str),
    )


@patch("modules.aws.ops_group_assignment.AWS_OPS_GROUP_NAME", "OpsGroup")
@patch("modules.aws.ops_group_assignment.logger")
@patch("modules.aws.ops_group_assignment.sso_admin")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.identity_store")
def test_execute_all_accounts_already_assigned(
    mock_identity_store, mock_organizations, mock_sso_admin, mock_logger
):
    mock_identity_store.get_group_id.return_value = "group-id"
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Status": "ACTIVE"},
        {"Id": "222222222222", "Status": "SUSPENDED"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = [
        {
            "AccountId": "111111111111",
            "PrincipalId": "group-id",
            "PrincipalType": "GROUP",
        }
    ]
    result = ops_group_assignment.execute()
    assert result["status"] == "ok"
    assert "already assigned" in result["message"]


@patch("modules.aws.ops_group_assignment.AWS_OPS_GROUP_NAME", "OpsGroup")
@patch("modules.aws.ops_group_assignment.logger")
@patch("modules.aws.ops_group_assignment.sso_admin")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.identity_store")
def test_execute_assignment_fails(
    mock_identity_store, mock_organizations, mock_sso_admin, mock_logger
):
    mock_identity_store.get_group_id.return_value = "group-id"
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "333333333333", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = []
    mock_sso_admin.create_account_assignment.return_value = False
    result = ops_group_assignment.execute()
    assert result["status"] == "failed"
    assert "Failed to assign" in result["message"]
