"""Unit tests for AWS ops group assignment handler."""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from modules.aws import ops_group_assignment


def _group_found(group_id: str = "group-123") -> OperationResult[str]:
    """Return the adapter result for a resolved ops group id."""
    return OperationResult.success(data=group_id)


def _feature_settings(group_name: str | None = "OpsGroup") -> MagicMock:
    """Return feature settings with the given ops group name."""
    settings = MagicMock()
    settings.AWS_OPS_GROUP_NAME = group_name
    return settings


def _arrange_accounts(
    mock_build_organizations_adapter: MagicMock,
    mock_build_sso_admin_adapter: MagicMock,
    accounts: list[dict[str, str]],
    assignments: list[dict[str, str]] | None = None,
) -> MagicMock:
    """Stub both listing calls as successful and every assignment as accepted; return the SSO Admin adapter mock."""
    mock_build_organizations_adapter.return_value.list_organization_accounts.return_value = OperationResult.success(data=accounts)
    sso_admin_adapter: MagicMock = mock_build_sso_admin_adapter.return_value
    sso_admin_adapter.list_account_assignments_for_principal.return_value = OperationResult.success(data=assignments or [])
    sso_admin_adapter.create_account_assignment.return_value = OperationResult.success(data=True)
    return sso_admin_adapter


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_return_none_when_feature_disabled(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_get_aws_feature_settings,
):
    """A disabled feature returns None without building any AWS adapter.

    Stub strategy: the ops group name setting is empty; both adapter factories
    are patched so a build (which performs AssumeRole) would be observable.
    """
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings(None)

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result is None
    mock_build_organizations_adapter.assert_not_called()
    mock_build_sso_admin_adapter.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_return_failed_when_group_not_found(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """A NOT_FOUND group lookup returns the 'not found' failed status and stops.

    Stub strategy: the adapter's get_group_id returns the NOT_FOUND result that
    classify_aws_error produces for ResourceNotFoundException. Asserts the
    lookup used the configured group name and that neither the Organizations
    nor the SSO Admin adapter is built without a group id.
    """
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
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
    mock_build_organizations_adapter.assert_not_called()
    mock_build_sso_admin_adapter.assert_not_called()


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
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_return_failed_with_lookup_error_when_group_lookup_fails(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
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
    missing, logs status and error_code, and builds no downstream adapter.
    """
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
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
    mock_build_organizations_adapter.assert_not_called()
    mock_build_sso_admin_adapter.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_return_failed_when_group_lookup_succeeds_without_group_id(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """A successful lookup with no group id is treated as a failed lookup.

    Stub strategy: the adapter returns a success result whose data is None.
    Asserts execute returns a failed status that does not claim the group is
    missing, and never builds the Organizations or SSO Admin adapter.
    """
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = OperationResult.success(data=None)

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    assert "not found" not in result["message"]
    mock_build_organizations_adapter.assert_not_called()
    mock_build_sso_admin_adapter.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_assign_group_to_unassigned_accounts(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Every unassigned active account is assigned and the success message names each one.

    Stub strategy: both listings succeed with two unassigned active accounts and
    every assignment is accepted. Asserts the assignments listing targets the
    group principal and the success message lists both accounts.
    """
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    sso_admin_adapter = _arrange_accounts(
        mock_build_organizations_adapter,
        mock_build_sso_admin_adapter,
        accounts=[
            {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
            {"Id": "222222222222", "Name": "Account2", "Status": "ACTIVE"},
        ],
    )

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "success"
    assert "assigned" in result["message"]
    assert "Account1" in result["message"]
    assert "Account2" in result["message"]
    assert sso_admin_adapter.create_account_assignment.call_count == 2
    sso_admin_adapter.list_account_assignments_for_principal.assert_called_once_with(
        principal_id="group-123", principal_type="GROUP"
    )


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_return_ok_when_all_accounts_assigned(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """An ops group already assigned to every active account returns ok without assigning."""
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    sso_admin_adapter = _arrange_accounts(
        mock_build_organizations_adapter,
        mock_build_sso_admin_adapter,
        accounts=[{"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"}],
        assignments=[{"AccountId": "111111111111"}],
    )

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "ok"
    assert "already assigned" in result["message"]
    sso_admin_adapter.create_account_assignment.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_skip_suspended_accounts(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Suspended accounts are not assigned."""
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    sso_admin_adapter = _arrange_accounts(
        mock_build_organizations_adapter,
        mock_build_sso_admin_adapter,
        accounts=[
            {"Id": "111111111111", "Name": "Account1", "Status": "SUSPENDED"},
            {"Id": "222222222222", "Name": "Account2", "Status": "ACTIVE"},
        ],
    )

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "success"
    sso_admin_adapter.create_account_assignment.assert_called_once()
    assert sso_admin_adapter.create_account_assignment.call_args.kwargs["account_id"] == "222222222222"


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_handle_account_missing_id(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """An account without an Id is skipped while accounts with an Id are still assigned."""
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    sso_admin_adapter = _arrange_accounts(
        mock_build_organizations_adapter,
        mock_build_sso_admin_adapter,
        accounts=[
            {"Name": "NoIdAccount", "Status": "ACTIVE"},
            {"Id": "222222222222", "Name": "Account2", "Status": "ACTIVE"},
        ],
    )

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert sso_admin_adapter.create_account_assignment.call_count == 1
    assert result["status"] == "success"


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_return_failed_when_no_unassigned_account_has_id(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """When no unassigned active account has an Id, a failed status is returned instead of raising.

    Stub strategy: the only unassigned active account lacks an Id, so the
    assignment loop assigns nothing. Asserts execute returns a failed status
    rather than raising on an unset status, and never calls the assignment API.
    """
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    sso_admin_adapter = _arrange_accounts(
        mock_build_organizations_adapter,
        mock_build_sso_admin_adapter,
        accounts=[{"Name": "NoIdAccount", "Status": "ACTIVE"}],
    )

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    sso_admin_adapter.create_account_assignment.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.logger")
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_return_failed_when_assignment_fails(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
    mock_logger,
):
    """An assignment error result is reported as failed with its cause logged.

    Stub strategy: create_account_assignment returns a TRANSIENT_ERROR result;
    the module logger is patched so the per-account bound logger (log.bind(...)
    inside the loop) can be inspected. Asserts the failed message names the
    account and the log carries the adapter's status, error_code and message.
    """
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    sso_admin_adapter = _arrange_accounts(
        mock_build_organizations_adapter,
        mock_build_sso_admin_adapter,
        accounts=[{"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"}],
    )
    sso_admin_adapter.create_account_assignment.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR,
        message="Rate exceeded",
        error_code="ThrottlingException",
    )

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    assert "Account1" in result["message"]
    mock_logger.bind.return_value.bind.return_value.error.assert_called_once_with(
        "failed_to_assign_ops_group_to_account",
        group_name="OpsGroup",
        status=OperationStatus.TRANSIENT_ERROR.value,
        error_code="ThrottlingException",
        error="Rate exceeded",
    )


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.logger")
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_return_failed_when_assignment_status_is_failed(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
    mock_logger,
):
    """A successful call whose creation status is FAILED counts as a failed assignment.

    Stub strategy: create_account_assignment returns success with data False,
    which is how the adapter reports an initial AWS status of FAILED. Asserts
    the run reports failed, names the account, and logs the assignment failure
    even though the SDK call itself succeeded.
    """
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    sso_admin_adapter = _arrange_accounts(
        mock_build_organizations_adapter,
        mock_build_sso_admin_adapter,
        accounts=[{"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"}],
    )
    sso_admin_adapter.create_account_assignment.return_value = OperationResult.success(data=False)

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    assert "Account1" in result["message"]
    account_log = mock_logger.bind.return_value.bind.return_value
    account_log.error.assert_called_once()
    assert account_log.error.call_args.args == ("failed_to_assign_ops_group_to_account",)


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_report_failed_when_any_assignment_fails_and_continue(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """An earlier assignment failure is not masked by a later success.

    Stub strategy: the first assignment returns an error result and the second
    succeeds. Asserts both accounts are attempted (the loop continues past a
    failure) and the run reports failed, naming only the account that failed.
    """
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    sso_admin_adapter = _arrange_accounts(
        mock_build_organizations_adapter,
        mock_build_sso_admin_adapter,
        accounts=[
            {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
            {"Id": "222222222222", "Name": "Account2", "Status": "ACTIVE"},
        ],
    )
    sso_admin_adapter.create_account_assignment.side_effect = [
        OperationResult.error(OperationStatus.PERMANENT_ERROR, message="Conflict", error_code="ConflictException"),
        OperationResult.success(data=True),
    ]

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    assert "Account1" in result["message"]
    assert "Account2" not in result["message"]
    assert sso_admin_adapter.create_account_assignment.call_count == 2


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_use_correct_permission_set(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """The group is assigned with the write permission set as a GROUP principal."""
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    sso_admin_adapter = _arrange_accounts(
        mock_build_organizations_adapter,
        mock_build_sso_admin_adapter,
        accounts=[{"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"}],
    )

    # Act
    ops_group_assignment.execute()

    # Assert
    sso_admin_adapter.create_account_assignment.assert_called_once_with(
        user_id="group-123",
        account_id="111111111111",
        permission_set="write",
        principal_type="GROUP",
    )


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_handle_multiple_accounts_with_mixed_status(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
):
    """Only active accounts not already assigned are assigned."""
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    sso_admin_adapter = _arrange_accounts(
        mock_build_organizations_adapter,
        mock_build_sso_admin_adapter,
        accounts=[
            {"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"},
            {"Id": "222222222222", "Name": "Account2", "Status": "SUSPENDED"},
            {"Id": "333333333333", "Name": "Account3", "Status": "ACTIVE"},
            {"Id": "444444444444", "Name": "Account4", "Status": "CLOSED"},
        ],
        assignments=[{"AccountId": "111111111111"}],
    )

    # Act
    result = ops_group_assignment.execute()

    # Assert
    sso_admin_adapter.create_account_assignment.assert_called_once()
    assert sso_admin_adapter.create_account_assignment.call_args.kwargs["account_id"] == "333333333333"
    assert result["status"] == "success"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "error_code", "error_message"),
    [
        (OperationStatus.TRANSIENT_ERROR, "ThrottlingException", "Rate exceeded"),
        (OperationStatus.UNAUTHORIZED, "AccessDeniedException", "Not authorized to list accounts"),
        (OperationStatus.NOT_FOUND, "AWSOrganizationsNotInUseException", "Organization not found"),
    ],
    ids=["transient", "unauthorized", "not_found"],
)
@patch("modules.aws.ops_group_assignment.logger")
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_return_failed_when_list_organization_accounts_fails(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
    mock_logger,
    status,
    error_code,
    error_message,
):
    """A failed organization account listing returns a failed status carrying the adapter message.

    Stub strategy: list_organization_accounts returns an error result for each
    classified failure family; the module logger is patched to inspect the
    bound logger. Asserts the cause reaches the admin, status and error_code are
    logged, and no assignment listing or assignment is attempted.
    """
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    mock_build_organizations_adapter.return_value.list_organization_accounts.return_value = OperationResult.error(
        status,
        message=error_message,
        error_code=error_code,
    )
    sso_admin_adapter = mock_build_sso_admin_adapter.return_value

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    assert error_message in result["message"]
    mock_logger.bind.return_value.error.assert_called_once_with(
        "organization_accounts_lookup_failed",
        group_name="OpsGroup",
        status=status.value,
        error_code=error_code,
        error=error_message,
    )
    sso_admin_adapter.list_account_assignments_for_principal.assert_not_called()
    sso_admin_adapter.create_account_assignment.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.ops_group_assignment.logger")
@patch("modules.aws.ops_group_assignment.get_aws_feature_settings")
@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")
@patch("modules.aws.ops_group_assignment.build_organizations_adapter")
@patch("modules.aws.ops_group_assignment.build_sso_admin_adapter")
def test_should_return_failed_when_list_account_assignments_fails(
    mock_build_sso_admin_adapter,
    mock_build_organizations_adapter,
    mock_build_adapter,
    mock_get_aws_feature_settings,
    mock_logger,
):
    """A failed account assignments listing returns a failed status carrying the adapter message.

    Stub strategy: the organization listing succeeds and
    list_account_assignments_for_principal returns an UNAUTHORIZED result; the
    module logger is patched to inspect the bound logger. Asserts the cause
    reaches the admin, status and error_code are logged, and no assignment is
    attempted against a partial view of existing assignments.
    """
    # Arrange
    mock_get_aws_feature_settings.return_value = _feature_settings()
    mock_build_adapter.return_value.get_group_id.return_value = _group_found()
    sso_admin_adapter = _arrange_accounts(
        mock_build_organizations_adapter,
        mock_build_sso_admin_adapter,
        accounts=[{"Id": "111111111111", "Name": "Account1", "Status": "ACTIVE"}],
    )
    sso_admin_adapter.list_account_assignments_for_principal.return_value = OperationResult.error(
        OperationStatus.UNAUTHORIZED,
        message="Not authorized to list assignments",
        error_code="AccessDeniedException",
    )

    # Act
    result = ops_group_assignment.execute()

    # Assert
    assert result["status"] == "failed"
    assert "Not authorized to list assignments" in result["message"]
    mock_logger.bind.return_value.error.assert_called_once_with(
        "ops_group_account_assignments_lookup_failed",
        group_name="OpsGroup",
        status=OperationStatus.UNAUTHORIZED.value,
        error_code="AccessDeniedException",
        error="Not authorized to list assignments",
    )
    sso_admin_adapter.create_account_assignment.assert_not_called()
