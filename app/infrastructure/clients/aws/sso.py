"""AWS SSO Admin client wrappers.

Thin wrappers around `execute_aws_api_call` that return OperationResult.
"""

from typing import Optional

from infrastructure.clients.aws.client import execute_aws_api_call
from infrastructure.operations.result import OperationResult


def create_account_assignment(
    user_id: str,
    account_id: str,
    permission_set_arn: str,
    instance_arn: str,
    role_arn: Optional[str] = None,
    principal_type: str = "USER",
    **kwargs
) -> OperationResult:
    params = {
        "InstanceArn": instance_arn,
        "TargetId": account_id,
        "TargetType": "AWS_ACCOUNT",
        "PermissionSetArn": permission_set_arn,
        "PrincipalType": principal_type,
        "PrincipalId": user_id,
    }
    return execute_aws_api_call(
        "sso-admin",
        "create_account_assignment",
        role_arn=role_arn,
        **params,
        **kwargs,
    )


def delete_account_assignment(
    user_id: str,
    account_id: str,
    permission_set_arn: str,
    instance_arn: str,
    role_arn: Optional[str] = None,
    **kwargs
) -> OperationResult:
    params = {
        "InstanceArn": instance_arn,
        "TargetId": account_id,
        "TargetType": "AWS_ACCOUNT",
        "PermissionSetArn": permission_set_arn,
        "PrincipalType": "USER",
        "PrincipalId": user_id,
    }
    return execute_aws_api_call(
        "sso-admin",
        "delete_account_assignment",
        role_arn=role_arn,
        **params,
        **kwargs,
    )


def list_account_assignments_for_principal(
    principal_id: str,
    instance_arn: str,
    role_arn: Optional[str] = None,
    principal_type: str = "USER",
    **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "sso-admin",
        "list_account_assignments",
        InstanceArn=instance_arn,
        PrincipalId=principal_id,
        PrincipalType=principal_type,
        role_arn=role_arn,
        **kwargs,
    )
