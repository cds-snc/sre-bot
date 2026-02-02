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
from typing import Any, Dict, List, Optional, Mapping

import structlog
from core.config import settings
from integrations.aws.client_next import execute_aws_api_call
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

# Configuration from settings
AWS_IDENTITY_STORE_ID = settings.aws.INSTANCE_ID
ROLE_ARN = settings.aws.ORG_ROLE_ARN

logger = structlog.get_logger()


# User Management Functions


def get_user(
    user_id: str,
    **kwargs,
) -> OperationResult:
    """
    Get a user from AWS Identity Store by user ID.

    Args:
        user_id (str): The user ID to retrieve
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="describe_user",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        UserId=user_id,
        role_arn=ROLE_ARN,
        **kwargs,
    )


def get_user_by_username(
    username: str,
    **kwargs,
) -> OperationResult:
    """
    Get a user ID by username (email).

    Args:
        username (str): The username (typically email) to search for
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
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
        **kwargs,
    )


def list_users(
    **kwargs,
) -> OperationResult:
    """
    List all users from AWS Identity Store.

    Args:
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="list_users",
        keys=["Users"],
        role_arn=ROLE_ARN,
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        MaxResults=100,
        force_paginate=True,
        **kwargs,
    )


def create_user(
    email: str,
    first_name: str,
    family_name: str,
    **kwargs,
) -> OperationResult:
    """
    Create a new user in AWS Identity Store.

    Args:
        email (str): The email address (username) for the user
        first_name (str): The user's first name
        family_name (str): The user's family name
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
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


def delete_user(user_id: str, **kwargs) -> OperationResult:
    """
    Delete a user from AWS Identity Store.

    Args:
        user_id (str): The user ID to delete
        **kwargs: Additional parameters for the API call

    Returns:
        bool: True if deletion was successful, False otherwise
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="delete_user",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        UserId=user_id,
        role_arn=ROLE_ARN,
        **kwargs,
    )


# Group Management Functions (Read-only - groups managed via Terraform)


def get_group(
    group_id: str,
    **kwargs,
) -> OperationResult:
    """
    Get a group from AWS Identity Store by group ID.

    Args:
        group_id (str): The group ID to retrieve
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="describe_group",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        GroupId=group_id,
        role_arn=ROLE_ARN,
        **kwargs,
    )


def get_group_by_name(
    group_name: str,
    **kwargs,
) -> OperationResult:
    """
    Get a group ID by group name (display name).

    Args:
        group_name (str): The group display name to search for
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
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
        **kwargs,
    )


def list_groups(
    **kwargs,
) -> OperationResult:
    """
    List all groups from AWS Identity Store.

    Args:
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.

    Example:
        ```
        result = list_groups()
        if result.is_success:
            groups = result.data  # List of groups
        else:
            logger.error("Failed to list groups", error=result.error)
        # Filters can be applied, e.g.:
        filters = [
            {
                "AttributePath": "DisplayName",
                "AttributeValue": "Group-Name", # Supports exact match only
            }
        ]
        result = list_groups(Filters=filters)
        ```
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="list_groups",
        keys=["Groups"],
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        MaxResults=100,
        role_arn=ROLE_ARN,
        force_paginate=True,
        **kwargs,
    )


# Group Membership Management Functions


def create_group_membership(group_id: str, user_id: str, **kwargs) -> OperationResult:
    """
    Create a group membership in AWS Identity Store.

    Args:
        group_id (str): The group ID
        user_id (str): The user ID
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="create_group_membership",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        GroupId=group_id,
        MemberId={"UserId": user_id},
        role_arn=ROLE_ARN,
        **kwargs,
    )


def delete_group_membership(membership_id: str, **kwargs) -> OperationResult:
    """
    Delete a group membership from AWS Identity Store.

    Args:
        membership_id (str): The membership ID to delete
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="delete_group_membership",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        MembershipId=membership_id,
        role_arn=ROLE_ARN,
        **kwargs,
    )


def get_group_membership_id(
    group_id: str,
    user_id: str,
    **kwargs,
) -> OperationResult:
    """
    Get the membership ID for a user in a group.

    Args:
        group_id (str): The group ID; either a UUID or display name
        user_id (str): The user ID; either a UUID or username, typically email
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="get_group_membership_id",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        GroupId=group_id,
        MemberId={"UserId": user_id},
        role_arn=ROLE_ARN,
        **kwargs,
    )


def list_group_memberships(group_id: str, **kwargs) -> OperationResult:
    """
    List all memberships for a specific group.

    Args:
        group_id (str): The group ID
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="list_group_memberships",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        GroupId=group_id,
        keys=["GroupMemberships"],
        role_arn=ROLE_ARN,
        force_paginate=True,
        **kwargs,
    )


def list_group_memberships_for_member(user_id: str, **kwargs) -> OperationResult:
    """
    List all group memberships for a specific user.

    Args:
        user_id (str): The user ID
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="list_group_memberships_for_member",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        MemberId={"UserId": user_id},
        keys=["GroupMemberships"],
        role_arn=ROLE_ARN,
        force_paginate=True,
        **kwargs,
    )


def is_member_in_groups(
    user_id: str,
    group_ids: List[str],
    **kwargs,
) -> OperationResult:
    """
    Check if a user is a member of specific groups.

    Args:
        user_id (str): The user ID
        group_ids (List[str]): List of group IDs to check
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response model for external API integrations.
    """

    return execute_aws_api_call(
        service_name="identitystore",
        method="is_member_in_groups",
        IdentityStoreId=AWS_IDENTITY_STORE_ID,
        MemberId={"UserId": user_id},
        GroupIds=group_ids,
        role_arn=ROLE_ARN,
        **kwargs,
    )


# Utility Functions


def healthcheck() -> bool:
    """
    Check the health of the AWS Identity Store integration.

    Returns:
        bool: True if the integration is healthy, False otherwise
    """
    try:
        # Simple test: try to list users (should work if credentials/config are correct)
        result: OperationResult = list_users()
        logger.info(
            "identity_store_healthcheck",
            status="healthy" if result.is_success else "unhealthy",
        )
        return result.is_success
    except Exception as error:  # pylint: disable=broad-except
        logger.exception("identity_store_healthcheck_failed", error=str(error))
        return False


# Batch Operations (leveraging the enhanced error handling)


def get_batch_users(user_ids: List[str], **kwargs) -> OperationResult:
    """
    Get multiple users by their IDs using individual API calls with enhanced error handling.

    Args:
        user_ids (List[str]): List of user IDs to retrieve
        **kwargs: Additional parameters for the API calls

    Returns:
        OperationResult: Standardized response model for external API operations.
    """
    results = {}
    errors = []
    for user_id in user_ids:
        response = get_user(user_id, **kwargs)
        if response.is_success:
            results[user_id] = response.data
        else:
            results[user_id] = None
            errors.append(
                {"user_id": user_id, "error": response.message or response.error_code}
            )
    if errors:
        return OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message=f"Failed to fetch {len(errors)} user(s)",
            error_code="batch_user_fetch_failed",
            data=results,
        )
    return OperationResult.success(
        data=results, message="All users fetched successfully"
    )


def get_batch_groups(group_ids: List[str], **kwargs) -> OperationResult:
    """
    Get multiple groups by their IDs using individual API calls with enhanced error handling.

    Args:
        group_ids (List[str]): List of group IDs to retrieve
        **kwargs: Additional parameters for the API calls

    Returns:
        OperationResult: Standardized response model for external API operations.
    """
    results = {}
    errors = []
    for group_id in group_ids:
        response = get_group(group_id, **kwargs)
        if response.is_success:
            results[group_id] = response.data
        else:
            results[group_id] = None
            errors.append(
                {"group_id": group_id, "error": response.message or response.error_code}
            )
    if errors:
        return OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message=f"Failed to fetch {len(errors)} group(s)",
            error_code="batch_group_fetch_failed",
            data=results,
        )

    return OperationResult.success(
        data=results, message="All groups fetched successfully"
    )


def _fetch_group_memberships_parallel(
    group_ids: List[str], max_workers: int = 10, **kwargs
) -> Dict[str, List[Dict[str, Any]]]:
    """Parallel helper function to fetch memberships for multiple groups."""
    memberships_by_group = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_gid = {
            executor.submit(list_group_memberships, gid, **kwargs): gid
            for gid in group_ids
        }
        # Collect results as they complete
        for future in as_completed(future_to_gid):
            gid = future_to_gid[future]
            try:
                response = future.result()
                if isinstance(response, OperationResult):
                    if response.is_success and isinstance(response.data, list):
                        memberships_by_group[gid] = response.data
                    else:
                        logger.warning(
                            "group_memberships_fetch_error",
                            group_id=gid,
                            error=response.message or response.error_code,
                        )
                        memberships_by_group[gid] = []
                else:
                    # Unexpected type, log and fallback
                    logger.warning(
                        "group_memberships_fetch_error",
                        group_id=gid,
                        error="Unexpected response type",
                    )
                    memberships_by_group[gid] = []
            except Exception as error:
                logger.warning(
                    "group_memberships_fetch_error",
                    group_id=gid,
                    error=str(error),
                )
                memberships_by_group[gid] = []

    return memberships_by_group


def _assemble_groups_with_memberships(
    groups: List[Dict],
    memberships_by_group: Dict[str, List[Dict[str, Any]]],
    users_by_id: Mapping[str, Optional[Dict[str, Any]]],
    tolerate_errors: bool,
) -> List[Dict[str, Any]]:
    """Helper function to assemble final groups with memberships and user details."""
    groups_with_memberships = []

    for group in groups:
        if not isinstance(group, dict):
            continue

        group_id = group.get("GroupId")
        if not isinstance(group_id, str):
            continue
        memberships = memberships_by_group.get(group_id) or []  # Always a list
        error_info = None

        if (
            not memberships
            and memberships_by_group.get(group_id) is None
            and tolerate_errors
        ):
            error_info = "No members found or error in member fetch."

        processed_memberships = []
        for membership in memberships:
            membership_copy = dict(membership)
            user_id = membership.get("MemberId", {}).get("UserId")

            if user_id and user_id in users_by_id:
                user_details = users_by_id[user_id]
                if user_details:
                    # Add user details to the membership
                    membership_copy["UserDetails"] = user_details

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
    groups_kwargs: Optional[Dict[str, Any]] = None,
    memberships_kwargs: Optional[Dict[str, Any]] = None,
    users_kwargs: Optional[Dict[str, Any]] = None,
    tolerate_errors: bool = False,
) -> OperationResult:
    """
    List all groups in the AWS Identity Store with their memberships

    Args:
        groups_filters (List, optional): A list of filter functions to apply to groups.
            Example: [lambda g: g['DisplayName'].lower().startswith('product-name')]
        tolerate_errors (bool, optional): If True, groups with member fetch errors are
            included without members.

    Returns:
        List[Dict]: A list of group objects with members. Groups without members are
            excluded unless tolerate_errors is True.
    """
    logger.info(
        "listing_groups_with_memberships",
        groups_kwargs=groups_kwargs,
        memberships_kwargs=memberships_kwargs,
        users_kwargs=users_kwargs,
        groups_filters=groups_filters,
        tolerate_errors=tolerate_errors,
    )

    # 1. Fetch all groups
    response: OperationResult = list_groups(**(groups_kwargs or {}))
    if response.is_success and isinstance(response.data, list):
        groups: List[Dict[str, Any]] = response.data
    else:
        return OperationResult.permanent_error(
            message="Failed to list groups",
            error_code="list_groups_failed",
        )

    logger.info("groups_listed", count=len(groups))

    # 2. Apply filters if provided
    if groups_filters:
        for groups_filter in groups_filters:
            groups = [g for g in groups if groups_filter(g)]
        logger.info("groups_filtered", count=len(groups), groups_filters=groups_filters)

    # 3. Batch fetch group memberships using our utility functions
    group_ids = [g["GroupId"] for g in groups if "GroupId" in g]
    memberships_by_group = _fetch_group_memberships_parallel(
        group_ids, **memberships_kwargs or {}
    )

    # 5. Batch fetch all user details using our utility function
    response = list_users(**(users_kwargs or {}))
    if not response.is_success:
        return OperationResult.permanent_error(
            message="Failed to list users",
            error_code="list_users_failed",
        )
    if isinstance(response.data, list):
        users: List[Dict[str, Any]] = response.data
    else:
        users = []
    logger.info("users_fetched", count=len(users))
    users_by_id = {str(u.get("UserId", "")): u for u in users if u.get("UserId")}
    groups_with_memberships = _assemble_groups_with_memberships(
        groups, memberships_by_group, users_by_id, tolerate_errors
    )

    logger.info("groups_with_memberships_listed", count=len(groups_with_memberships))
    return OperationResult.success(
        data=groups_with_memberships,
        message="Groups with memberships listed successfully",
    )
