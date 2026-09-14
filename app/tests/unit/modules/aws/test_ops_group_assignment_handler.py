"""Unit tests for AWS ops group assignment handler."""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from modules.aws import ops_group_assignment


def _group_found(group_id: str = "group-123") -> OperationResult[str]:
    """Return the adapter result for a resolved ops group id."""
    return OperationResult.success(data=group_id)


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
def test_should_return_none_when_feature_disabled(mock_get_aws_feature_settings):
    """Test execute returns None when feature is disabled."""
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = None
    mock_get_aws_feature_settings.return_value = mock_feature_settings

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result is None


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_return_failed_when_group_not_found(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """A NOT_FOUND group lookup returns the 'not found' failed status and stops.

    Stub strategy: the adapter's get_group_id returns the NOT_FOUND result that
    classify_aws_error produces for ResourceNotFoundException. Asserts the
    lookup used the configured group name and that no account listing or
    assignment is attempted without a group id.
    """
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = OperationResult.error(
        OperationStatus.NOT_FOUND,
        message="Group not found",
        error_code="ResourceNotFoundException",
    )

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    assert result["message"] == "Ops group 'OpsGroup' not found in AWS Identity Center."
    mock_build_adapter.return_value.get_group_id.assert_called_once_with("OpsGroup")
    mock_organizations.list_organization_accounts.assert_not_called()
    mock_sso_admin.list_account_assignments_for_principal.assert_not_called()
    mock_sso_admin.create_account_assignment.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "error_code", "error_message"),
    [
        (OperationStatus.TRANSIENT_ERROR, "ThrottlingException", "Rate exceeded"),
        (OperationStatus.UNAUTHORIZED, "AccessDeniedException", "User is not authorized"),
        (OperationStatus.PERMANENT_ERROR, "ValidationException", "Invalid identity store id"),
    ],
    ids=["transient", "unauthorized", "permanent"],
)
@patch("modules.aws.ops_group_assignment.logger")
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_return_failed_with_lookup_error_when_group_lookup_fails(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
    mock_logger,
    status,
    error_code,
    error_message,
):
    """A non-NOT_FOUND lookup failure is reported as a lookup error, not as 'not found'.

    Stub strategy: the adapter's get_group_id returns an error result for each
    non-NOT_FOUND failure family; the module logger is patched so the bound
    logger's error call can be inspected. Asserts the failed status carries the
    adapter's message (so admins see the real cause), never claims the group is
    missing, logs status and error_code, and makes no downstream AWS calls.
    """
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = OperationResult.error(
        status,
        message=error_message,
        error_code=error_code,
    )

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    assert error_message in result["message"]
    assert "not found" not in result["message"]
    mock_logger.bind.return_value.error.assert_called_once_with(
        "ops_group_lookup_failed",
        group_name="OpsGroup",
        status=status.value,
        error_code=error_code,
        error=error_message,
    )
    mock_organizations.list_organization_accounts.assert_not_called()
    mock_sso_admin.list_account_assignments_for_principal.assert_not_called()
    mock_sso_admin.create_account_assignment.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_return_failed_when_group_lookup_succeeds_without_group_id(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """A successful lookup with no group id is treated as a failed lookup.

    Stub strategy: the adapter returns a success result whose data is None.
    Asserts execute returns a failed status that does not claim the group is
    missing, and never lists accounts or calls SSO Admin with a None principal.
    """
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = OperationResult.success(data=None)

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    assert "not found" not in result["message"]
    mock_organizations.list_organization_accounts.assert_not_called()
    mock_sso_admin.list_account_assignments_for_principal.assert_not_called()
    mock_sso_admin.create_account_assignment.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_assign_group_to_unassigned_accounts(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Test execute assigns ops group to unassigned accounts."""
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
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
    mock_sso_admin.list_account_assignments_for_principal.assert_called_once_with(
        principal_id="group-123", principal_type="GROUP"
    )


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_return_ok_when_all_accounts_assigned(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Test execute returns ok when all accounts already assigned."""
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = [{"AccountId": "111111111111"}]

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "ok"
    assert "already assigned" in result["message"]


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_skip_suspended_accounts(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Test execute skips suspended accounts."""
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
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
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_handle_account_missing_id(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Test execute handles accounts missing ID gracefully."""
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
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
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_return_failed_when_assignment_fails(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Test execute returns failed status when assignment fails."""
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
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
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_use_correct_permission_set(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Test execute uses correct permission set when assigning."""
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = []
    mock_sso_admin.create_account_assignment.return_value = True

    # Act
    ops_group_assignment.execute()

    # Assert
    call_args = mock_sso_admin.create_account_assignment.call_args
    assert call_args[1]["user_id"] == "group-123"
    assert call_args[1]["permission_set"] == "write"
    assert call_args[1]["principal_type"] == "GROUP"


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_handle_multiple_accounts_with_mixed_status(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Test execute handles mixed account statuses correctly."""
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
        {"Id": "222222222222", "Name": "Account2", "Status": "SUSPENDED"},
        {"Id": "333333333333", "Name": "Account3", "Status": "ACTIVE"},
        {"Id": "444444444444", "Name": "Account4", "Status": "CLOSED"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = [{"AccountId": "111111111111"}]
    mock_sso_admin.create_account_assignment.return_value = True

    # Act
    result = ops_group_assignment.execute()

    # Assert
    # Only Account3 should be assigned (Account1 already assigned, Account2/4 not ACTIVE)
    assert mock_sso_admin.create_account_assignment.call_count == 1
    assert result["status"] == "success"


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_raise_when_list_organization_accounts_returns_false(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Test execute surfaces a TypeError when organizations returns False.

    Stub strategy: list_organization_accounts returns the literal False that
    handle_aws_api_errors produces on error; the list comprehension over
    organizations_accounts pins today's crash on a non-iterable bool.
    """
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    mock_organizations.list_organization_accounts.return_value = False
    mock_sso_admin.list_account_assignments_for_principal.return_value = []

    # Act & Assert
    with pytest.raises(TypeError):
        ops_group_assignment.execute()


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.organizations")
@patch("modules.aws.ops_group_assignment.sso_admin")
def test_should_raise_when_list_account_assignments_returns_false(
    mock_sso_admin,
    mock_organizations,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Test execute surfaces a TypeError when sso_admin returns False.

    Stub strategy: list_account_assignments_for_principal returns the literal False;
    the set comprehension over account_assignments pins today's crash on a
    non-iterable bool.
    """
    # Arrange
    mock_feature_settings = MagicMock()
    mock_feature_settings.AWS_OPS_GROUP_NAME = "OpsGroup"
    mock_get_aws_feature_settings.return_value = mock_feature_settings
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
    ]
    mock_sso_admin.list_account_assignments_for_principal.return_value = False

    # Act & Assert
    with pytest.raises(TypeError):
        ops_group_assignment.execute()
