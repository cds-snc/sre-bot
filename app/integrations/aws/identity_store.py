import os
import logging
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors
from utils import filters

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
        str: The unique ID of the user created.
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

    Returns:
        bool: True if the user was deleted successfully, False otherwise.
    """
    kwargs = resolve_identity_store_id(kwargs)
    kwargs.update({"UserId": user_id})
    response = execute_aws_api_call("identitystore", "delete_user", **kwargs)
    del response["ResponseMetadata"]
    return response == {}


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
    return execute_aws_api_call("identitystore", "get_user_id", **kwargs)["UserId"]


@handle_aws_api_errors
def describe_user(user_id, **kwargs):
    """Retrieves the user details of the user

    Args:
        user_id (str): The user ID of the user.
        **kwargs: Additional keyword arguments for the API call.
    """
    kwargs = resolve_identity_store_id(kwargs)
    kwargs.update({"UserId": user_id})
    response = execute_aws_api_call("identitystore", "describe_user", **kwargs)
    del response["ResponseMetadata"]
    return response


@handle_aws_api_errors
def list_users(**kwargs):
    """Retrieves all users from the AWS Identity Center (identitystore)"""
    kwargs = resolve_identity_store_id(kwargs)
    return execute_aws_api_call(
        "identitystore", "list_users", paginated=True, keys=["Users"], **kwargs
    )


@handle_aws_api_errors
def get_group_id(group_name, **kwargs):
    """Retrieves the group ID of the group

    Args:
        group_name (str): The name of the group.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        str: The group ID of the group.
    """
    kwargs = resolve_identity_store_id(kwargs)
    kwargs.update(
        {
            "AlternateIdentifier": {
                "UniqueAttribute": {
                    "AttributePath": "displayName",
                    "AttributeValue": group_name,
                },
            }
        }
    )
    response = execute_aws_api_call("identitystore", "get_group_id", **kwargs)
    return response["GroupId"] if response else False


@handle_aws_api_errors
def list_groups(**kwargs):
    """Retrieves all groups from the AWS Identity Center (identitystore)
    
    Args:
        **kwargs: Additional keyword arguments for the API call.
        
    Returns:
        list: A list of group objects."""
    kwargs = resolve_identity_store_id(kwargs)
    response = execute_aws_api_call(
        "identitystore", "list_groups", paginated=True, keys=["Groups"], **kwargs
    )
    return response if response else []


@handle_aws_api_errors
def create_group_membership(group_id, user_id, **kwargs):
    """Creates a group membership in the AWS Identity Center (identitystore)

    Args:
        group_id (str): The group ID of the group.
        user_id (str): The user ID of the user.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        str: The membership ID of the created group membership.
    """
    kwargs = resolve_identity_store_id(kwargs)
    kwargs.update({"GroupId": group_id, "MemberId": {"UserId": user_id}})
    response = execute_aws_api_call(
        "identitystore", "create_group_membership", **kwargs
    )
    return response["MembershipId"] if response else False


@handle_aws_api_errors
def delete_group_membership(membership_id, **kwargs):
    """Deletes a group membership from the AWS Identity Center (identitystore)

    Args:
        membership_id (str): The membership ID of the group membership, which is the unique identifier representing the assignment of a user to a group.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        bool: True if the group membership was deleted successfully, False otherwise.
    """
    kwargs = resolve_identity_store_id(kwargs)
    kwargs.update({"MembershipId": membership_id})
    response = execute_aws_api_call(
        "identitystore", "delete_group_membership", **kwargs
    )
    del response["ResponseMetadata"]
    return response == {}


@handle_aws_api_errors
def get_group_membership_id(group_id, user_id, **kwargs):
    """Retrieves the group membership ID of the group membership

    Args:
        group_id (str): The group ID of the group.
        user_id (str): The user ID of the user.
        **kwargs: Additional keyword arguments for the API call.
    """
    kwargs = resolve_identity_store_id(kwargs)
    kwargs.update({"GroupId": group_id, "MemberId": {"UserId": user_id}})
    response = execute_aws_api_call(
        "identitystore", "get_group_membership_id", **kwargs
    )
    return response["MembershipId"] if response else False


@handle_aws_api_errors
def list_group_memberships(group_id, **kwargs):
    """Retrieves all group memberships from the AWS Identity Center  (identitystore)

    Args:
        group_id (str): The group ID of the group.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        list: A list of group membership objects."""
    kwargs = resolve_identity_store_id(kwargs)
    response = execute_aws_api_call(
        "identitystore",
        "list_group_memberships",
        GroupId=group_id,
        **kwargs,
    )
    return response["GroupMemberships"] if response else []


@handle_aws_api_errors
def list_groups_with_memberships(**kwargs):
    """Retrieves groups with their members from the AWS Identity Center (identitystore)

    Args:
        **kwargs: Additional keyword arguments for the API call. (passed to list_groups)

    Returns:
        list: A list of group objects with their members.
    """
    members_details = kwargs.pop("members_details", True)
    groups_filters = kwargs.pop("filters", [])
    groups = list_groups(**kwargs)

    if not groups:
        return []
    for filter in groups_filters:
        groups = filters.filter_by_condition(groups, filter)

    for group in groups:
        group["GroupMemberships"] = list_group_memberships(group["GroupId"])
        if group["GroupMemberships"] and members_details:
            for membership in group["GroupMemberships"]:
                membership["MemberId"] = describe_user(membership["MemberId"]["UserId"])

    return groups
