"""AWS Organizations client wrappers using infrastructure client pattern.

These functions standardize responses to OperationResult and accept
role_arn as an explicit parameter for cross-account access.
"""

from typing import Optional

from infrastructure.clients.aws.client import execute_aws_api_call
from infrastructure.operations.result import OperationResult


def list_organization_accounts(
    role_arn: Optional[str] = None, **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "organizations",
        "list_accounts",
        keys=["Accounts"],
        force_paginate=True,
        role_arn=role_arn,
        **kwargs,
    )


def get_account_details(
    account_id: str, role_arn: Optional[str] = None, **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "organizations",
        "describe_account",
        AccountId=account_id,
        role_arn=role_arn,
        **kwargs,
    )


def get_account_id_by_name(
    account_name: str, role_arn: Optional[str] = None, **kwargs
) -> OperationResult:
    # Return the full OperationResult so callers can inspect status/data
    return list_organization_accounts(role_arn=role_arn, **kwargs)
