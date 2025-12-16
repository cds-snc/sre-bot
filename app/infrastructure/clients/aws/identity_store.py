"""AWS Identity Store client wrappers using OperationResult pattern.

These functions are thin wrappers around `execute_aws_api_call` and accept
configuration parameters instead of reading module-level settings.
"""

from typing import Any, Dict, List, Optional

from infrastructure.clients.aws.client import execute_aws_api_call
from infrastructure.operations.result import OperationResult


def get_user(
    user_id: str, identity_store_id: str, role_arn: Optional[str] = None, **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "identitystore",
        "describe_user",
        IdentityStoreId=identity_store_id,
        UserId=user_id,
        role_arn=role_arn,
        **kwargs,
    )


def get_user_by_username(
    username: str, identity_store_id: str, role_arn: Optional[str] = None, **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "identitystore",
        "get_user_id",
        IdentityStoreId=identity_store_id,
        AlternateIdentifier={
            "UniqueAttribute": {"AttributePath": "userName", "AttributeValue": username}
        },
        role_arn=role_arn,
        **kwargs,
    )


def list_users(
    identity_store_id: str, role_arn: Optional[str] = None, **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "identitystore",
        "list_users",
        IdentityStoreId=identity_store_id,
        role_arn=role_arn,
        **kwargs,
    )


def create_user(
    user_attrs: Dict[str, Any],
    identity_store_id: str,
    role_arn: Optional[str] = None,
    **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "identitystore",
        "create_user",
        IdentityStoreId=identity_store_id,
        **user_attrs,
        role_arn=role_arn,
        **kwargs,
    )


def delete_user(
    user_id: str, identity_store_id: str, role_arn: Optional[str] = None, **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "identitystore",
        "delete_user",
        IdentityStoreId=identity_store_id,
        UserId=user_id,
        role_arn=role_arn,
        **kwargs,
    )
