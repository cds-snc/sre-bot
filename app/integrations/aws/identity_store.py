import os
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

INSTANCE_ID = os.environ.get("AWS_SSO_INSTANCE_ID", "")
INSTANCE_ARN = os.environ.get("AWS_SSO_INSTANCE_ARN", "")
ROLE_ARN = os.environ.get("AWS_SSO_ROLE_ARN", "")


@handle_aws_api_errors
def list_users(**kwargs):
    """Retrieves all users from the AWS Identity Center (identitystore)"""
    if "IdentityStoreId" not in kwargs:
        kwargs["IdentityStoreId"] = INSTANCE_ID
    return execute_aws_api_call(
        "identitystore", "list_users", paginated=True, keys=["Users"], **kwargs
    )


@handle_aws_api_errors
def list_groups(**kwargs):
    """Retrieves all groups from the AWS Identity Center (identitystore)"""
    if "IdentityStoreId" not in kwargs:
        kwargs["IdentityStoreId"] = INSTANCE_ID
    return execute_aws_api_call(
        "identitystore", "list_groups", paginated=True, keys=["Groups"], **kwargs
    )


@handle_aws_api_errors
def list_group_memberships(group_id, **kwargs):
    """Retrieves all group memberships from the AWS Identity Center  (identitystore)"""
    if "IdentityStoreId" not in kwargs:
        kwargs["IdentityStoreId"] = INSTANCE_ID
    return execute_aws_api_call(
        "identitystore",
        "list_group_memberships",
        ["GroupMemberships"],
        GroupId=group_id,
        **kwargs,
    )


@handle_aws_api_errors
def list_groups_with_membership():
    """Retrieves all groups with their members from the AWS Identity Center (identitystore)"""
    groups = list_groups()
    for group in groups:
        group["GroupMemberships"] = list_group_memberships(
            group["GroupId"]
        )

    return groups
