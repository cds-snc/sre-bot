"""AWS Identity Store module"""

from core.config import settings
from core.logging import get_module_logger

import pandas as pd
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors
from utils import filters

INSTANCE_ID = settings.aws.INSTANCE_ID
ROLE_ARN = settings.aws.ORG_ROLE_ARN

logger = get_module_logger()


def resolve_identity_store_id(kwargs):
    """Resolve IdentityStoreId and add it to kwargs if not present."""
    if "IdentityStoreId" not in kwargs:
        kwargs["IdentityStoreId"] = kwargs.get("identity_store_id", INSTANCE_ID)
        kwargs.pop("identity_store_id", None)
    if kwargs["IdentityStoreId"] is None:
        error_message = "IdentityStoreId must be provided either as a keyword argument or as the AWS_SSO_INSTANCE_ID environment variable"
        logger.error(error_message)
        raise ValueError(error_message)
    return kwargs


def healthcheck():
    """Check the health of the AWS integration.

    Returns:
        bool: True if the integration is healthy, False otherwise.
    """
    healthy = False
    try:
        response = list_users()
        healthy = True if response else False
        logger.info(f"AWS IdentityStore healthcheck result: {response}")
    except Exception as error:
        logger.error(f"AWS IdentityStore healthcheck failed: {error}")
    return healthy


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
    params = {
        "IdentityStoreId": kwargs.get("IdentityStoreId"),
        "UserName": email,
        "Emails": [{"Value": email, "Type": "WORK", "Primary": True}],
        "Name": {"GivenName": first_name, "FamilyName": family_name},
        "DisplayName": f"{first_name} {family_name}",
        "role_arn": ROLE_ARN,
    }
    return execute_aws_api_call("identitystore", "create_user", **params)["UserId"]


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
    params = {
        "UserId": user_id,
        "IdentityStoreId": kwargs.get("IdentityStoreId"),
        "role_arn": ROLE_ARN,
    }
    response = execute_aws_api_call("identitystore", "delete_user", **params)
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
    params = {
        "IdentityStoreId": kwargs.get("IdentityStoreId"),
        "AlternateIdentifier": {
            "UniqueAttribute": {
                "AttributePath": "userName",
                "AttributeValue": user_name,
            },
        },
        "role_arn": ROLE_ARN,
    }
    return execute_aws_api_call("identitystore", "get_user_id", **params)["UserId"]


@handle_aws_api_errors
def describe_user(user_id, **kwargs):
    """Retrieves the user details of the user

    Args:
        user_id (str): The user ID of the user.
        **kwargs: Additional keyword arguments for the API call.
    """
    kwargs = resolve_identity_store_id(kwargs)
    params = {
        "IdentityStoreId": kwargs.get("IdentityStoreId"),
        "UserId": user_id,
        "role_arn": ROLE_ARN,
    }
    response = execute_aws_api_call("identitystore", "describe_user", **params)
    for key in ["ResponseMetadata", "IdentityStoreId"]:
        del response[key]
    return response


@handle_aws_api_errors
def list_users(**kwargs):
    """Retrieves all users from the AWS Identity Center (identitystore)"""
    kwargs = resolve_identity_store_id(kwargs)
    params = {"IdentityStoreId": kwargs.get("IdentityStoreId"), "role_arn": ROLE_ARN}
    if "filters" in kwargs:
        params["Filters"] = kwargs["filters"]
    return execute_aws_api_call(
        "identitystore", "list_users", paginated=True, keys=["Users"], **params
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
    params = {
        "IdentityStoreId": kwargs.get("IdentityStoreId"),
        "AlternateIdentifier": {
            "UniqueAttribute": {
                "AttributePath": "displayName",
                "AttributeValue": group_name,
            },
        },
        "role_arn": ROLE_ARN,
    }
    response = execute_aws_api_call("identitystore", "get_group_id", **params)
    return response["GroupId"] if response else False


@handle_aws_api_errors
def list_groups(**kwargs):
    """Retrieves all groups from the AWS Identity Center (identitystore)

    Args:
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        list: A list of group objects."""
    kwargs = resolve_identity_store_id(kwargs)
    params = {
        "IdentityStoreId": kwargs.get("IdentityStoreId"),
        "role_arn": ROLE_ARN,
    }
    if "filters" in kwargs:
        params["Filters"] = kwargs["filters"]
    response = execute_aws_api_call(
        "identitystore", "list_groups", paginated=True, keys=["Groups"], **params
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
    params = {
        "IdentityStoreId": kwargs.get("IdentityStoreId"),
        "GroupId": group_id,
        "MemberId": {"UserId": user_id},
        "role_arn": ROLE_ARN,
    }
    response = execute_aws_api_call(
        "identitystore", "create_group_membership", **params
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
    params = {
        "IdentityStoreId": kwargs.get("IdentityStoreId"),
        "MembershipId": membership_id,
        "role_arn": ROLE_ARN,
    }
    response = execute_aws_api_call(
        "identitystore", "delete_group_membership", **params
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
    params = {
        "IdentityStoreId": kwargs.get("IdentityStoreId"),
        "GroupId": group_id,
        "MemberId": {"UserId": user_id},
        "role_arn": ROLE_ARN,
    }
    response = execute_aws_api_call(
        "identitystore", "get_group_membership_id", **params
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
    params = {
        "IdentityStoreId": kwargs.get("IdentityStoreId"),
        "GroupId": group_id,
        "keys": ["GroupMemberships"],
        "paginated": True,
        "role_arn": ROLE_ARN,
    }
    response = execute_aws_api_call(
        "identitystore",
        "list_group_memberships",
        **params,
    )
    return response if response else []


@handle_aws_api_errors
def list_groups_with_memberships(
    groups_filters: list | None = None,
    tolerate_errors: bool = False,
):
    """Retrieves groups with their members from the AWS Identity Center (identitystore)

    Args:
        group_members (bool): Include group members in the response. Default is True.
        members_details (bool): Include the details of the members. Default is True.
        include_empty_groups (bool): Include groups without members. Default is True.
        groups_filters (list): A list of filters to apply to the groups. Default is None.
        **kwargs: Additional keyword arguments for the API call. (passed to list_groups)

    Returns:
        list: A list of group objects with their members. Any group without members will not be included.
    """
    groups = list_groups()

    if not groups:
        return []

    if groups_filters is not None:
        for groups_filter in groups_filters:
            groups = filters.filter_by_condition(groups, groups_filter)
    logger.info(f"Found {len(groups)} groups in AWS Identity Store.")

    filtered_groups = [
        {
            k: v
            for k, v in group.items()
            if k in ["GroupId", "DisplayName", "Description", "IdentityStoreId"]
        }
        for group in groups
    ]

    users = list_users()
    logger.info(f"Found {len(users)} users in AWS Identity Store.")

    groups_with_memberships = []
    for group in filtered_groups:
        error_occurred = False
        logger.info(f"Getting members for group: {group['DisplayName']}")
        try:
            memberships = list_group_memberships(group["GroupId"])
        except Exception as error:
            logger.warning(
                f"Error getting members for group {group['GroupId']}: {error}"
            )
            continue
        for membership in memberships:
            member_details = {}
            try:
                member_details = next(
                    member
                    for member in users
                    if member["UserId"] == membership["MemberId"]["UserId"]
                )
            except Exception as error:
                logger.warning(
                    f"Error getting details for member {membership['MemberId']['UserId']}: {error}"
                )
                error_occurred = True
                if not tolerate_errors:
                    break
            if member_details:
                membership["MemberId"].update(member_details)
        if memberships and (not error_occurred or tolerate_errors):
            group["GroupMemberships"] = memberships
            groups_with_memberships.append(group)
    return groups_with_memberships


def convert_aws_groups_members_to_dataframe(groups):
    """Converts a list of AWS groups with members to a DataFrame.

    Args:
        groups (list): A list of group objects with members.

    Returns:
        DataFrame: A DataFrame with group members.
    """
    flattened_data = []
    for group in groups:
        group_id = group.get("GroupId")
        group_name = group.get("DisplayName")
        group_description = group.get("Description")
        group_identity_store_id = group.get("IdentityStoreId")

        for membership in group.get("GroupMemberships", []):
            member = membership.get("MemberId", {})
            member_user_id = member.get("UserId")
            member_email = member.get("UserName")
            member_given_name = member.get("Name", {}).get("GivenName")
            member_family_name = member.get("Name", {}).get("FamilyName")
            member_display_name = member.get("DisplayName")

            flattened_record = {
                "group_id": group_id,
                "group_name": group_name,
                "group_description": group_description,
                "group_identity_store_id": group_identity_store_id,
                "member_user_id": member_user_id,
                "member_email": member_email,
                "member_given_name": member_given_name,
                "member_family_name": member_family_name,
                "member_display_name": member_display_name,
            }
            flattened_data.append(flattened_record)

    return pd.DataFrame(flattened_data)
