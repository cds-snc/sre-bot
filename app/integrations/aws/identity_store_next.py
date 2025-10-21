"""
AWS Identity Store Next Module

This module provides streamlined functions to work with AWS Identity Store APIs,
leveraging the new client_next.py module with enhanced error handling and consistent response formatting.

Functions focused on user and group membership management:
- User management: get_user, list_users, create_user, delete_user
- Group querying: get_group, list_groups (read-only, groups managed via Terraform)
- Membership management: create_group_membership, delete_group_membership, list_group_memberships
- Utility functions: get_user_id, get_group_id, get_group_membership_id, is_member_in_groups

Note: Group creation/deletion and permission management are handled via Terraform,
not through this module.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from core.config import settings
from core.logging import get_module_logger
from integrations.aws.client_next import execute_aws_api_call

# Configuration from settings
AWS_IDENTITY_STORE_ID = settings.aws.INSTANCE_ID
ROLE_ARN = settings.aws.ORG_ROLE_ARN

logger = get_module_logger()


# User Management Functions


def get_user(
    user_id: str,
    non_critical: bool = True,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """
    Get a user from AWS Identity Store by user ID.

    Args:
        user_id (str): The user ID to retrieve
        identity_store_id (str, optional): Identity Store ID
        non_critical (bool): Mark as non-critical (returns None on error)
        **kwargs: Additional parameters for the API call

    Returns:
        Optional[Dict]: User details or None if not found/error
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="describe_user",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        UserId=user_id,
        role_arn=ROLE_ARN,
        non_critical=non_critical,
        **kwargs,
    )


def get_user_by_username(
    username: str,
    non_critical: bool = True,
    **kwargs,
) -> Optional[str]:
    """
    Get a user ID by username (email).

    Args:
        username (str): The username (typically email) to search for
        identity_store_id (str, optional): Identity Store ID
        non_critical (bool): Mark as non-critical (returns None on error)
        **kwargs: Additional parameters for the API call

    Returns:
        Optional[str]: User ID if found, None otherwise
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="get_user_id",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        AlternateIdentifier={
            "UniqueAttribute": {
                "AttributePath": "userName",
                "AttributeValue": username,
            }
        },
        role_arn=ROLE_ARN,
        non_critical=non_critical,
        **kwargs,
    )

    return result.get("UserId") if result else None


def list_users(
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    List all users from AWS Identity Store.

    Args:
        identity_store_id (str, optional): Identity Store ID
        filters (List[Dict], optional): Filters to apply to the user list
        **kwargs: Additional parameters for the API call

    Returns:
        List[Dict]: List of user objects
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="list_users",
        keys=["Users"],
        role_arn=ROLE_ARN,
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        MaxResults=100,
        force_paginate=True,
        **kwargs,
    )

    return result if result else []


def create_user(
    email: str,
    first_name: str,
    family_name: str,
    **kwargs,
) -> Optional[str]:
    """
    Create a new user in AWS Identity Store.

    Args:
        email (str): The email address (username) for the user
        first_name (str): The user's first name
        family_name (str): The user's family name
        identity_store_id (str, optional): Identity Store ID
        **kwargs: Additional parameters for the API call

    Returns:
        Optional[str]: The created user ID or None on error
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="create_user",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        UserName=email,
        Emails=[{"Value": email, "Type": "WORK", "Primary": True}],
        Name={"GivenName": first_name, "FamilyName": family_name},
        DisplayName=f"{first_name} {family_name}",
        role_arn=ROLE_ARN,
        **kwargs,
    )

    return result.get("UserId") if result else None


def delete_user(user_id: str, **kwargs) -> bool:
    """
    Delete a user from AWS Identity Store.

    Args:
        user_id (str): The user ID to delete
        identity_store_id (str, optional): Identity Store ID
        **kwargs: Additional parameters for the API call

    Returns:
        bool: True if deletion was successful, False otherwise
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="delete_user",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        UserId=user_id,
        role_arn=ROLE_ARN,
        **kwargs,
    )

    # AWS delete operations return empty dict on success
    return result is not None


# Group Management Functions (Read-only - groups managed via Terraform)


def get_group(
    group_id: str,
    non_critical: bool = True,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """
    Get a group from AWS Identity Store by group ID.

    Args:
        group_id (str): The group ID to retrieve
        identity_store_id (str, optional): Identity Store ID
        non_critical (bool): Mark as non-critical (returns None on error)
        **kwargs: Additional parameters for the API call

    Returns:
        Optional[Dict]: Group details or None if not found/error
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="describe_group",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        GroupId=group_id,
        role_arn=ROLE_ARN,
        non_critical=non_critical,
        **kwargs,
    )


def get_group_by_name(
    group_name: str,
    non_critical: bool = True,
    **kwargs,
) -> Optional[str]:
    """
    Get a group ID by group name (display name).

    Args:
        group_name (str): The group display name to search for
        identity_store_id (str, optional): Identity Store ID
        non_critical (bool): Mark as non-critical (returns None on error)
        **kwargs: Additional parameters for the API call

    Returns:
        Optional[str]: Group ID if found, None otherwise
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="get_group_id",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        AlternateIdentifier={
            "UniqueAttribute": {
                "AttributePath": "displayName",
                "AttributeValue": group_name,
            }
        },
        role_arn=ROLE_ARN,
        non_critical=non_critical,
        **kwargs,
    )

    return result.get("GroupId") if result else None


def list_groups(
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    List all groups from AWS Identity Store.

    Args:
        identity_store_id (str, optional): Identity Store ID
        **kwargs: Additional parameters for the API call

    Returns:
        List[Dict]: List of group objects
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="list_groups",
        keys=["Groups"],
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        MaxResults=100,
        role_arn=ROLE_ARN,
        force_paginate=True,
        **kwargs,
    )

    return result if result else []


# Group Membership Management Functions


def create_group_membership(group_id: str, user_id: str, **kwargs) -> Optional[str]:
    """
    Create a group membership in AWS Identity Store.

    Args:
        group_id (str): The group ID
        user_id (str): The user ID
        identity_store_id (str, optional): Identity Store ID
        **kwargs: Additional parameters for the API call

    Returns:
        Optional[str]: The membership ID or None on error
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="create_group_membership",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        GroupId=group_id,
        MemberId={"UserId": user_id},
        role_arn=ROLE_ARN,
        **kwargs,
    )

    return result.get("MembershipId") if result else None


def delete_group_membership(membership_id: str, **kwargs) -> bool:
    """
    Delete a group membership from AWS Identity Store.

    Args:
        membership_id (str): The membership ID to delete
        identity_store_id (str, optional): Identity Store ID
        **kwargs: Additional parameters for the API call

    Returns:
        bool: True if deletion was successful, False otherwise
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="delete_group_membership",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        MembershipId=membership_id,
        role_arn=ROLE_ARN,
        **kwargs,
    )

    # AWS delete operations return empty dict on success
    return result is not None


def get_group_membership_id(
    group_id: str,
    user_id: str,
    non_critical: bool = True,
    **kwargs,
) -> Optional[str]:
    """
    Get the membership ID for a user in a group.

    Args:
        group_id (str): The group ID
        user_id (str): The user ID
        identity_store_id (str, optional): Identity Store ID
        non_critical (bool): Mark as non-critical (returns None on error)
        **kwargs: Additional parameters for the API call

    Returns:
        Optional[str]: The membership ID or None if not found/error
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="get_group_membership_id",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        GroupId=group_id,
        MemberId={"UserId": user_id},
        role_arn=ROLE_ARN,
        non_critical=non_critical,
        **kwargs,
    )

    return result.get("MembershipId") if result else None


def list_group_memberships(group_id: str, **kwargs) -> List[Dict[str, Any]]:
    """
    List all memberships for a specific group.

    Args:
        group_id (str): The group ID
        identity_store_id (str, optional): Identity Store ID
        **kwargs: Additional parameters for the API call

    Returns:
        List[Dict]: List of group membership objects
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="list_group_memberships",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        GroupId=group_id,
        keys=["GroupMemberships"],
        role_arn=ROLE_ARN,
        force_paginate=True,
        **kwargs,
    )

    return result if result else []


def list_group_memberships_for_member(user_id: str, **kwargs) -> List[Dict[str, Any]]:
    """
    List all group memberships for a specific user.

    Args:
        user_id (str): The user ID
        identity_store_id (str, optional): Identity Store ID
        **kwargs: Additional parameters for the API call

    Returns:
        List[Dict]: List of group membership objects for the user
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="list_group_memberships_for_member",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        MemberId={"UserId": user_id},
        keys=["GroupMemberships"],
        role_arn=ROLE_ARN,
        force_paginate=True,
        **kwargs,
    )

    return result if result else []


def is_member_in_groups(
    user_id: str,
    group_ids: List[str],
    **kwargs,
) -> Dict[str, bool]:
    """
    Check if a user is a member of specific groups.

    Args:
        user_id (str): The user ID
        group_ids (List[str]): List of group IDs to check
        identity_store_id (str, optional): Identity Store ID
        **kwargs: Additional parameters for the API call

    Returns:
        Dict[str, bool]: Mapping of group ID to membership status
    """

    result = execute_aws_api_call(
        service_name="identitystore",
        method="is_member_in_groups",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        MemberId={"UserId": user_id},
        GroupIds=group_ids,
        role_arn=ROLE_ARN,
        **kwargs,
    )

    if result and "Results" in result:
        return {item["GroupId"]: item["MembershipExists"] for item in result["Results"]}
    return {group_id: False for group_id in group_ids}


# Utility Functions


def healthcheck() -> bool:
    """
    Check the health of the AWS Identity Store integration.

    Returns:
        bool: True if the integration is healthy, False otherwise
    """
    try:
        # Simple test: try to list users (should work if credentials/config are correct)
        result = list_users()
        healthy = result is not None
        logger.info(
            "identity_store_healthcheck",
            status="healthy" if healthy else "unhealthy",
        )
        return healthy
    except Exception as error:
        logger.exception("identity_store_healthcheck_failed", error=str(error))
        return False


# Batch Operations (leveraging the enhanced error handling)


def get_batch_users(
    user_ids: List[str], **kwargs
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Get multiple users by their IDs using individual API calls with enhanced error handling.

    Args:
        user_ids (List[str]): List of user IDs to retrieve
        identity_store_id (str, optional): Identity Store ID
        **kwargs: Additional parameters for the API calls

    Returns:
        Dict[str, Optional[Dict]]: Mapping of user ID to user details (None if not found/error)
    """
    results = {}
    for user_id in user_ids:
        try:
            user_data = get_user(user_id, non_critical=True, **kwargs)
            results[user_id] = user_data
        except Exception as e:
            logger.warning(
                "get_batch_users_individual_error", user_id=user_id, error=str(e)
            )
            results[user_id] = None

    logger.info(
        "get_batch_users_completed",
        requested=len(user_ids),
        successful=len([v for v in results.values() if v is not None]),
        failed=len([v for v in results.values() if v is None]),
    )

    return results


def get_batch_groups(
    group_ids: List[str], **kwargs
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Get multiple groups by their IDs using individual API calls with enhanced error handling.

    Args:
        group_ids (List[str]): List of group IDs to retrieve
        identity_store_id (str, optional): Identity Store ID
        **kwargs: Additional parameters for the API calls

    Returns:
        Dict[str, Optional[Dict]]: Mapping of group ID to group details (None if not found/error)
    """
    results = {}
    for group_id in group_ids:
        try:
            group_data = get_group(group_id, non_critical=True, **kwargs)
            results[group_id] = group_data
        except Exception as e:
            logger.warning(
                "get_batch_groups_individual_error", group_id=group_id, error=str(e)
            )
            results[group_id] = None

    logger.info(
        "get_batch_groups_completed",
        requested=len(group_ids),
        successful=len([v for v in results.values() if v is not None]),
        failed=len([v for v in results.values() if v is None]),
    )

    return results


def _fetch_group_memberships_parallel(
    group_ids: List[str], tolerate_errors: bool, max_workers: int = 10
) -> Dict[str, Optional[List]]:
    """Parallel helper function to fetch memberships for multiple groups."""
    memberships_by_group = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_gid = {
            executor.submit(list_group_memberships, gid): gid for gid in group_ids
        }

        # Collect results as they complete
        for future in as_completed(future_to_gid):
            gid = future_to_gid[future]
            try:
                memberships_by_group[gid] = future.result()
            except Exception as error:
                logger.warning(
                    "group_memberships_fetch_error",
                    group_id=gid,
                    error=str(error),
                )
                memberships_by_group[gid] = [] if tolerate_errors else None

    return memberships_by_group


def _assemble_groups_with_memberships(
    groups: List[Dict],
    memberships_by_group: Dict[str, Optional[List]],
    users_by_id: Dict[str, Optional[Dict]],
    tolerate_errors: bool,
) -> List[Dict[str, Any]]:
    """Helper function to assemble final groups with memberships and user details."""
    groups_with_memberships = []

    for group in groups:
        if not isinstance(group, dict):
            continue

        group_id = group.get("GroupId")
        memberships = memberships_by_group.get(group_id, [])
        error_info = None

        if (
            not memberships
            and memberships_by_group.get(group_id) is None
            and tolerate_errors
        ):
            error_info = "No members found or error in member fetch."

        processed_memberships = []
        for membership in memberships or []:
            membership_copy = dict(membership)
            user_id = membership.get("MemberId", {}).get("UserId")

            if user_id and user_id in users_by_id:
                user_details = users_by_id[user_id]
                if user_details:
                    # Add user details to the membership
                    membership_copy["user_details"] = user_details
                    # Update MemberId with user details for backward compatibility
                    membership_copy["MemberId"].update(user_details)

            processed_memberships.append(membership_copy)

        group_obj = dict(group)
        group_obj["GroupMemberships"] = processed_memberships

        if error_info:
            group_obj["error"] = error_info

        # Only include groups with members, unless tolerate_errors is True
        if processed_memberships or tolerate_errors:
            groups_with_memberships.append(group_obj)

    return groups_with_memberships


def list_groups_with_memberships(
    groups_filters: Optional[List] = None,
    tolerate_errors: bool = False,
) -> List[Dict[str, Any]]:
    """
    List all groups in the AWS Identity Store with their memberships

    Args:
        groups_filters (List, optional): A list of filter functions to apply to groups.
            Example: [lambda g: g['DisplayName'].startswith('aws-')]
        tolerate_errors (bool, optional): If True, groups with member fetch errors are
            included without members.

    Returns:
        List[Dict]: A list of group objects with members. Groups without members are
            excluded unless tolerate_errors is True.
    """
    logger.info(
        "listing_groups_with_memberships",
        groups_filters=groups_filters,
        tolerate_errors=tolerate_errors,
    )

    # 1. Fetch all groups
    groups = list_groups()
    if not groups:
        return []

    logger.info("groups_listed", count=len(groups))

    # 2. Apply filters if provided
    if groups_filters:
        for groups_filter in groups_filters:
            groups = [g for g in groups if groups_filter(g)]
        logger.info("groups_filtered", count=len(groups), groups_filters=groups_filters)

    # 3. Batch fetch group memberships using our utility functions
    group_ids = [g["GroupId"] for g in groups if "GroupId" in g]
    memberships_by_group = _fetch_group_memberships_parallel(group_ids, tolerate_errors)
    logger.info("memberships_batch_fetched", count=len(memberships_by_group))

    # 5. Batch fetch all user details using our utility function
    users = list_users()
    logger.info("users_fetched", count=len(users))
    users_by_id = {str(u.get("UserId", "")): u for u in users if u.get("UserId")}
    groups_with_memberships = _assemble_groups_with_memberships(
        groups, memberships_by_group, users_by_id, tolerate_errors
    )

    logger.info("groups_with_memberships_listed", count=len(groups_with_memberships))
    return groups_with_memberships
