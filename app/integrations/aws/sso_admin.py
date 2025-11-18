from core.config import settings
from core.logging import get_module_logger
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors


logger = get_module_logger()

ROLE_ARN = settings.aws.ORG_ROLE_ARN
INSTANCE_ARN = settings.aws.INSTANCE_ARN
SYSTEM_ADMIN_PERMISSIONS = settings.aws.SYSTEM_ADMIN_PERMISSIONS
VIEW_ONLY_PERMISSIONS = settings.aws.VIEW_ONLY_PERMISSIONS


def get_predefined_permission_sets(permission_set_name):
    """Get the predefined permission sets for AWS SSO.

    Args:
        permission_set_name (str): The name of the predefined permission set.

    Returns:
        str: The ARN of the predefined permission set.
    """
    predefined_permission_sets = {
        "write": SYSTEM_ADMIN_PERMISSIONS,
        "read": VIEW_ONLY_PERMISSIONS,
    }

    return predefined_permission_sets.get(permission_set_name, permission_set_name)


@handle_aws_api_errors
def create_account_assignment(
    user_id, account_id, permission_set, principal_type="USER"
):
    """Create an account assignment for an AWS SSO user.

    Args:
        user_id (str): The ID of the user.
        account_id (str): The ID of the AWS account.
        permission_set (str): The ARN of the permission set or a predefined permission set.

    Returns:
        bool: Whether the account assignment was successful.
    """
    permissions_set_arn = get_predefined_permission_sets(permission_set)

    params = {
        "InstanceArn": INSTANCE_ARN,
        "TargetId": account_id,
        "TargetType": "AWS_ACCOUNT",
        "PermissionSetArn": permissions_set_arn,
        "PrincipalType": principal_type,
        "PrincipalId": user_id,
    }
    response = execute_aws_api_call(
        "sso-admin",
        "create_account_assignment",
        role_arn=ROLE_ARN,
        **params,
    )

    return response["AccountAssignmentCreationStatus"]["Status"] != "FAILED"


@handle_aws_api_errors
def delete_account_assignment(user_id, account_id, permission_set):
    """Delete an account assignment for an AWS IAM user.

    Args:
        user_id (str): The ID of the user.
        account_id (str): The ID of the AWS account.
        permission_set (str): The ARN of the permission set or a predefined permission set.

    Returns:
        bool: Whether the account assignment was successfully deleted.
    """
    permission_set_arn = get_predefined_permission_sets(permission_set)
    params = {
        "InstanceArn": INSTANCE_ARN,
        "TargetId": account_id,
        "TargetType": "AWS_ACCOUNT",
        "PermissionSetArn": permission_set_arn,
        "PrincipalType": "USER",
        "PrincipalId": user_id,
    }
    response = execute_aws_api_call(
        "sso-admin",
        "delete_account_assignment",
        role_arn=ROLE_ARN,
        **params,
    )
    return response["AccountAssignmentDeletionStatus"]["Status"] != "FAILED"


def list_account_assignments_for_principal(principal_id, principal_type="USER"):
    """List the account assignments for a given principal.

    Args:
        principal_id (str): The ID of the principal (user or group).
        principal_type (str): The type of the principal ("USER" or "GROUP"). Default is "USER".

    Returns:
        list: The list of account assignments.
    """
    params = {
        "InstanceArn": INSTANCE_ARN,
        "PrincipalType": principal_type,
        "PrincipalId": principal_id,
    }
    response = execute_aws_api_call(
        "sso-admin",
        "list_account_assignments_for_principal",
        paginated=True,
        role_arn=ROLE_ARN,
        keys=["AccountAssignments"],
        **params,
    )

    return response if response else []


@handle_aws_api_errors
def list_accounts_for_provisioned_permission_set(permission_set):
    """List the AWS accounts for a provisioned permission set.

    Args:
        permission_set_arn (str): The ARN of the permission set or a predefined permission set name (e.g., 'write').

    Returns:
        list: The list of AWS accounts.
    """
    permission_set_arn = get_predefined_permission_sets(permission_set)
    params = {
        "PermissionSetArn": permission_set_arn,
        "InstanceArn": INSTANCE_ARN,
    }
    response = execute_aws_api_call(
        "sso-admin",
        "list_accounts_for_provisioned_permission_set",
        paginated=True,
        role_arn=ROLE_ARN,
        keys=["AccountIds"],
        **params,
    )

    return response if response else []
