"""Unit tests for AWS ops group assignment handler."""

import pytest
from unittest.mock import MagicMock, patch

from modules.aws import ops_group_assignment


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_settings")
def test_should_return_none_when_feature_disabled(mock_get_settings):
    """Test execute returns None when feature is disabled."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_OPS_GROUP_NAME = None
    mock_get_settings.return_value = mock_settings

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result is None


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_settings")
@patch("modules.aws.ops_group_assignment.identity_store")
def test_should_return_failed_when_group_not_found(
    mock_identity_store, mock_get_settings
):
    """Test execute returns failed status when ops group not found."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_settings.return_value = mock_settings
    mock_identity_store.get_group_id.return_value = None

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    assert "not found" in result["message"]
    mock_identity_store.get_group_id.assert_called_once_with("OpsGroup")


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_settings")
@patch("modules.aws.ops_group_assignment.identity_store")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_assign_group_to_unassigned_accounts(
    mock_sso_admin, mock_organizations, mock_identity_store, mock_get_settings
):
    """Test execute assigns ops group to unassigned accounts."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_settings.return_value = mock_settings
    mock_identity_store.get_group_id.return_value = "group-123"
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
        {"Id": "222222222222", "Name": "Account2", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = []
    mock_sso_admin.create_account_assignment.return_value = True

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "success"
    assert "assigned" in result["message"]
    assert mock_sso_admin.create_account_assignment.call_count == 2


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_settings")
@patch("modules.aws.ops_group_assignment.identity_store")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_return_ok_when_all_accounts_assigned(
    mock_sso_admin, mock_organizations, mock_identity_store, mock_get_settings
):
    """Test execute returns ok when all accounts already assigned."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_settings.return_value = mock_settings
    mock_identity_store.get_group_id.return_value = "group-123"
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = [
        {"AccountId": "111111111111"}
    ]

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "ok"
    assert "already assigned" in result["message"]


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_settings")
@patch("modules.aws.ops_group_assignment.identity_store")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_skip_suspended_accounts(
    mock_sso_admin, mock_organizations, mock_identity_store, mock_get_settings
):
    """Test execute skips suspended accounts."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_settings.return_value = mock_settings
    mock_identity_store.get_group_id.return_value = "group-123"
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Name": "Account1", "Status": "SUSPENDED"},
        {"Id": "222222222222", "Name": "Account2", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = []
    mock_sso_admin.create_account_assignment.return_value = True

    # Act
    result = ops_group_assignment.execute()

    # Assert
    # Only active account should be assigned
    assert result["status"] == "success"
    assert mock_sso_admin.create_account_assignment.call_count == 1


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_settings")
@patch("modules.aws.ops_group_assignment.identity_store")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_handle_account_missing_id(
    mock_sso_admin, mock_organizations, mock_identity_store, mock_get_settings
):
    """Test execute handles accounts missing ID gracefully."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_settings.return_value = mock_settings
    mock_identity_store.get_group_id.return_value = "group-123"
    mock_organizations.list_organization_accounts.return_value = [
        {"Name": "NoIdAccount", "Status": "ACTIVE"},
        {"Id": "222222222222", "Name": "Account2", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = []
    mock_sso_admin.create_account_assignment.return_value = True

    # Act
    result = ops_group_assignment.execute()

    # Assert
    # Only account with ID should be assigned
    assert mock_sso_admin.create_account_assignment.call_count == 1
    assert result["status"] == "success"


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_settings")
@patch("modules.aws.ops_group_assignment.identity_store")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_return_failed_when_assignment_fails(
    mock_sso_admin, mock_organizations, mock_identity_store, mock_get_settings
):
    """Test execute returns failed status when assignment fails."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_settings.return_value = mock_settings
    mock_identity_store.get_group_id.return_value = "group-123"
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = []
    mock_sso_admin.create_account_assignment.return_value = False

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    assert "Failed" in result["message"]


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_settings")
@patch("modules.aws.ops_group_assignment.identity_store")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_use_correct_permission_set(
    mock_sso_admin, mock_organizations, mock_identity_store, mock_get_settings
):
    """Test execute uses correct permission set when assigning."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_settings.return_value = mock_settings
    mock_identity_store.get_group_id.return_value = "group-123"
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = []
    mock_sso_admin.create_account_assignment.return_value = True

    # Act
    ops_group_assignment.execute()

    # Assert
    call_args = mock_sso_admin.create_account_assignment.call_args
    assert call_args[1]["permission_set"] == "write"
    assert call_args[1]["principal_type"] == "GROUP"


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_settings")
@patch("modules.aws.ops_group_assignment.identity_store")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_handle_multiple_accounts_with_mixed_status(
    mock_sso_admin, mock_organizations, mock_identity_store, mock_get_settings
):
    """Test execute handles mixed account statuses correctly."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_settings.return_value = mock_settings
    mock_identity_store.get_group_id.return_value = "group-123"
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
        {"Id": "222222222222", "Name": "Account2", "Status": "SUSPENDED"},
        {"Id": "333333333333", "Name": "Account3", "Status": "ACTIVE"},
        {"Id": "444444444444", "Name": "Account4", "Status": "CLOSED"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = [
        {"AccountId": "111111111111"}
    ]
    mock_sso_admin.create_account_assignment.return_value = True

    # Act
    result = ops_group_assignment.execute()

    # Assert
    # Only Account3 should be assigned (Account1 already assigned, Account2/4 not ACTIVE)
    assert mock_sso_admin.create_account_assignment.call_count == 1
    assert result["status"] == "success"
