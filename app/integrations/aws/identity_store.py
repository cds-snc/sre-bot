import os
import logging
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

INSTANCE_ID = os.environ.get("AWS_SSO_INSTANCE_ID", "")
INSTANCE_ARN = os.environ.get("AWS_SSO_INSTANCE_ARN", "")
ROLE_ARN = os.environ.get("AWS_SSO_ROLE_ARN", "")

logger = logging.getLogger(__name__)


def resolve_identity_store_id(kwargs):
    """Resolve IdentityStoreId and add it to kwargs if not present."""
    if "IdentityStoreId" not in kwargs:
        kwargs["IdentityStoreId"] = kwargs.get(
            "identity_store_id", os.environ.get("AWS_SSO_INSTANCE_ID", None)
        )
        kwargs.pop("identity_store_id", None)
    if kwargs["IdentityStoreId"] is None:
        error_message = "IdentityStoreId must be provided either as a keyword argument or as the AWS_SSO_INSTANCE_ID environment variable"
        logger.error(error_message)
        raise ValueError(error_message)
    return kwargs


@handle_aws_api_errors
def create_user(email, first_name, family_name, **kwargs):
    """Creates a new user in the AWS Identity Center (identitystore)

    Args:
        email (str): The email address of the user.
        first_name (str): The first name of the user.
        family_name (str): The family name of the user.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        str: The user ID of the created user.
    """
    kwargs = resolve_identity_store_id(kwargs)
    kwargs.update(
        {
            "UserName": email,
            "Emails": [{"Value": email, "Type": "WORK", "Primary": True}],
            "Name": {"GivenName": first_name, "FamilyName": family_name},
            "DisplayName": f"{first_name} {family_name}",
        }
    )
    return execute_aws_api_call("identitystore", "create_user", **kwargs)["UserId"]


@handle_aws_api_errors
def delete_user(user_id, **kwargs):
    """Deletes a user from the AWS Identity Center (identitystore)

    Args:
        user_id (str): The user ID of the user.
        **kwargs: Additional keyword arguments for the API call.
    """
    kwargs = resolve_identity_store_id(kwargs)
    kwargs.update({"UserId": user_id})
    result = execute_aws_api_call("identitystore", "delete_user", **kwargs)
    return True if result == {} else False


@handle_aws_api_errors
def get_user_id(user_name, **kwargs):
    """Retrieves the user ID of the current user

    Args:
        user_name (str): The user name of the user. Default is the primary email address.
        **kwargs: Additional keyword arguments for the API call.
    """
    kwargs = resolve_identity_store_id(kwargs)
    kwargs.update(
        {
            "AlternateIdentifier": {
                "UniqueAttribute": {
                    "AttributePath": "userName",
                    "AttributeValue": user_name,
                },
            }
        }
    )
    result = execute_aws_api_call("identitystore", "get_user_id", **kwargs)
    return result["UserId"] if result else False


@handle_aws_api_errors
def list_users(**kwargs):
    """Retrieves all users from the AWS Identity Center (identitystore)"""
    kwargs = resolve_identity_store_id(kwargs)
    return execute_aws_api_call(
        "identitystore", "list_users", paginated=True, keys=["Users"], **kwargs
    )


@handle_aws_api_errors
def list_groups(**kwargs):
    """Retrieves all groups from the AWS Identity Center (identitystore)"""
    kwargs = resolve_identity_store_id(kwargs)
    return execute_aws_api_call(
        "identitystore", "list_groups", paginated=True, keys=["Groups"], **kwargs
    )


@handle_aws_api_errors
def list_group_memberships(group_id, **kwargs):
    """Retrieves all group memberships from the AWS Identity Center  (identitystore)"""
    kwargs = resolve_identity_store_id(kwargs)
    return execute_aws_api_call(
        "identitystore",
        "list_group_memberships",
        ["GroupMemberships"],
        GroupId=group_id,
        **kwargs,
    )


@handle_aws_api_errors
def list_groups_with_memberships():
    """Retrieves all groups with their members from the AWS Identity Center (identitystore)"""
    groups = list_groups()
    for group in groups:
        group["GroupMemberships"] = list_group_memberships(group["GroupId"])

    return groups