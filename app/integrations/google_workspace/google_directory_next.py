"""
Google Directory module using simplified Google service functions.

"""

from typing import Dict, List, Optional, Tuple
from core.logging import get_module_logger
from integrations.google_workspace import google_service_next as google_service
from integrations.google_workspace.google_service_next import (
    execute_google_api_call,
    get_google_service,
    execute_batch_request,
)
import time
from integrations.google_workspace import google_directory, google_directory_next

GOOGLE_WORKSPACE_CUSTOMER_ID = google_service.GOOGLE_WORKSPACE_CUSTOMER_ID

logger = get_module_logger()


def get_user(user_key: str, **kwargs) -> Optional[dict]:
    """Get a user from Google Directory."""
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "users",
        "get",
        scopes=["https://www.googleapis.com/auth/admin.directory.user.readonly"],
        non_critical=True,
        userKey=user_key,
        **kwargs,
    )


def get_batch_users(user_keys: List[str], **kwargs) -> Dict[str, Optional[dict]]:
    """Get multiple users from Google Directory using batch requests."""
    service = get_google_service(
        "admin",
        "directory_v1",
        scopes=["https://www.googleapis.com/auth/admin.directory.user.readonly"],
    )
    requests = []
    for user_key in user_keys:
        req = service.users().get(userKey=user_key, **kwargs)
        requests.append((user_key, req))

    batch_result = execute_batch_request(service, requests)
    results = batch_result.get("results", {})
    users_by_key: Dict[str, Optional[dict]] = {}
    for user_key in user_keys:
        user_data = results.get(user_key)
        users_by_key[user_key] = user_data

    return users_by_key


def list_users(**kwargs) -> List[dict]:
    """List all users from Google Directory with integrated error handling and auto-pagination."""
    result = execute_google_api_call(
        "admin",
        "directory_v1",
        "users",
        "list",
        scopes=["https://www.googleapis.com/auth/admin.directory.user.readonly"],
        customer=GOOGLE_WORKSPACE_CUSTOMER_ID,
        **kwargs,
    )
    return result or []


def get_group(group_key: str, **kwargs) -> Optional[dict]:
    """Get a group from Google Directory with integrated error handling."""
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "groups",
        "get",
        scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
        non_critical=True,  # Group not found is acceptable
        groupKey=group_key,
        **kwargs,
    )


def get_batch_groups(group_keys: List[str], **kwargs) -> Dict[str, Optional[dict]]:
    """Get multiple groups from Google Directory using batch requests."""
    service = get_google_service(
        "admin",
        "directory_v1",
        scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
    )
    requests = []
    for group_key in group_keys:
        req = service.groups().get(groupKey=group_key, **kwargs)
        requests.append((group_key, req))

    batch_result = execute_batch_request(service, requests)
    results = batch_result.get("results", {})

    groups_by_key: Dict[str, Optional[dict]] = {}
    for group_key in group_keys:
        group = results.get(group_key)
        groups_by_key[group_key] = group

    return groups_by_key


def list_groups(**kwargs) -> List[dict]:
    """List all groups from Google Directory with integrated error handling and auto-pagination."""
    result = execute_google_api_call(
        "admin",
        "directory_v1",
        "groups",
        "list",
        scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
        customer=GOOGLE_WORKSPACE_CUSTOMER_ID,
        **kwargs,
    )
    return result or []


def get_member(group_key: str, member_key: str, **kwargs) -> Optional[dict]:
    """Get a member of a group from Google Directory with integrated error handling."""
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "get",
        scopes=[
            "https://www.googleapis.com/auth/admin.directory.group.member.readonly"
        ],
        non_critical=True,  # Member not found is acceptable
        groupKey=group_key,
        memberKey=member_key,
        **kwargs,
    )


def get_batch_members(group_keys: List[str], **kwargs) -> Dict[str, List[dict]]:
    """Get multiple groups' members using batch requests.

    Args:
        group_keys (List[str]): List of group keys to fetch members for.
        **kwargs: Additional keyword arguments for the members.list API call.

    Returns:
        Dict[str, List[dict]]: A dictionary mapping group keys to their members.
    """

    service = get_google_service(
        "admin",
        "directory_v1",
        scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
    )
    requests = []
    for group_key in group_keys:
        req = service.members().list(groupKey=group_key, **kwargs)
        requests.append((group_key, req))

    batch_result = execute_batch_request(service, requests)
    results = batch_result.get("results", {})

    members_by_group: Dict[str, List[dict]] = {}
    for group_key in group_keys:
        members = results.get(group_key)
        if not members:
            members_by_group[group_key] = []
            continue
        if isinstance(members, dict) and "members" in members:
            members_by_group[group_key] = members["members"]
        elif isinstance(members, list):
            members_by_group[group_key] = members
        else:
            members_by_group[group_key] = []

    return members_by_group


def list_members(group_key: str, **kwargs) -> List[dict]:
    """List all members of a group from Google Directory with integrated error handling and auto-pagination."""
    result = execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "list",
        scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
        non_critical=True,
        groupKey=group_key,
        **kwargs,
    )
    return result or []


def has_member(group_key: str, member_key: str, **kwargs) -> bool:
    """Check if a member exists in a group with integrated error handling."""
    member = execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "hasMember",
        scopes=[
            "https://www.googleapis.com/auth/admin.directory.group.member.readonly"
        ],
        non_critical=True,  # Member not found is acceptable
        groupKey=group_key,
        memberKey=member_key,
        **kwargs,
    )
    return member


def insert_member(
    group_key: str,
    email: str,
    role: str = "MEMBER",
    type_: str = "USER",
    member_body: Optional[dict] = None,
    **kwargs,
) -> Optional[dict]:
    """
    Insert a member into a group. Supports both simple and advanced usage.
    If member_body is provided, it overrides email/role/type_.
    """
    if member_body is None:
        body = {"email": email, "role": role, "type": type_}
    else:
        body = member_body

    return execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "insert",
        scopes=["https://www.googleapis.com/auth/admin.directory.group"],
        non_critical=True,
        groupKey=group_key,
        body=body,
        **kwargs,
    )


def list_groups_with_members(
    groups_filters: Optional[list] = None,
    groups_kwargs: Optional[dict] = None,
    members_kwargs: Optional[dict] = None,
    tolerate_errors: bool = False,
) -> list:
    """
    List all groups in the Google Workspace domain with their members.

    Args:
        groups_filters (list, optional): A list of filter functions to apply to groups. Example: [lambda g: g['email'].startswith('aws-')]
        groups_kwargs (dict, optional): Additional keyword arguments for listing groups.
        members_kwargs (dict, optional): Additional keyword arguments for listing members.
        tolerate_errors (bool, optional): If True, groups with member fetch errors are included without members.
    Returns:
        list: A list of group objects with members. Any group without members will not be included.
    """
    logger.info(
        "listing_groups_with_members",
        groups_kwargs=groups_kwargs,
        members_kwargs=members_kwargs,
        groups_filters=groups_filters,
    )
    # 1. Fetch groups
    groups = list_groups(**(groups_kwargs or {}))
    if not groups:
        return []

    logger.info("groups_listed", count=len(groups))
    # 2. Apply filters if provided
    if groups_filters:
        for groups_filter in groups_filters:
            groups = [g for g in groups if groups_filter(g)]
        logger.info("groups_filtered", count=len(groups), groups_filters=groups_filters)

    # 3. Batch fetch groups members
    group_emails = [g["email"] for g in groups if "email" in g]
    members_by_group = get_batch_members(group_emails)

    logger.info("members_batch_fetched", count=len(members_by_group))
    # 4. Collect unique member emails across all groups
    member_emails = {
        m["email"]
        for members in members_by_group.values()
        for m in members
        if "email" in m
    }

    # 5. Batch fetch all members details for all groups
    users_by_email = get_batch_users(list(member_emails)) if member_emails else {}
    logger.info("members_batch_fetched", count=len(users_by_email))

    # 6. Assemble final groups with members
    groups_with_members = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_email = group.get("email", {})
        members = members_by_group.get(group_email, [])
        error_info = None
        if not members and tolerate_errors:
            error_info = "No members found or error in member fetch."
        processed_members = []
        for m in members:
            member_copy = dict(m)
            email = m.get("email")
            if email and email in users_by_email:
                user_details = users_by_email[email]
                member_copy["user_details"] = user_details
                # BACKWARD COMPATIBILITY: Flatten user_details into top-level member dict
                # TODO: To be deprecated in future versions
                if isinstance(user_details, dict):
                    # Flatten user_details into the top-level member dict
                    for k, v in user_details.items():
                        if k not in member_copy:
                            member_copy[k] = v
            processed_members.append(member_copy)
        group_obj = dict(group) if isinstance(group, dict) else {}
        group_obj["members"] = processed_members
        group_obj["email"] = group_email
        if error_info:
            group_obj["error"] = error_info
        # Only include groups with members, unless tolerate_errors is True
        if processed_members or tolerate_errors:
            groups_with_members.append(group_obj)
    logger.info("groups_with_members_listed", count=len(groups_with_members))
    return groups_with_members


# Example 8: Performance comparison function
def performance_comparison_example():
    """
    Compare legacy and next-gen list_groups_with_members functions for the same query.
    Times each and returns summary of group/member counts and timing.
    """

    query = "email:aws-*"
    logger.info("starting_groups_with_members_comparison", query=query)

    # Legacy
    start_time = time.time()
    legacy_result = google_directory.list_groups_with_members(
        query=query,
    )
    legacy_time = time.time() - start_time

    # Next-gen
    start_time = time.time()
    next_result = google_directory_next.list_groups_with_members(
        groups_kwargs={"query": query, "maxResults": 3, "orderBy": "email"},
        tolerate_errors=True,
    )
    next_time = time.time() - start_time

    legacy_group_count = len(legacy_result)
    legacy_member_count = sum(len(g.get("members", [])) for g in legacy_result)
    next_group_count = len(next_result)
    next_member_count = sum(len(g.get("members", [])) for g in next_result)

    logger.info(
        "groups_with_members_comparison_results",
        legacy_group_count=legacy_group_count,
        legacy_member_count=legacy_member_count,
        legacy_time=legacy_time,
        next_group_count=next_group_count,
        next_member_count=next_member_count,
        next_time=next_time,
    )

    return {
        "legacy": {
            "group_count": legacy_group_count,
            "member_count": legacy_member_count,
            "time": legacy_time,
            "groups": legacy_result,
        },
        "next": {
            "group_count": next_group_count,
            "member_count": next_member_count,
            "time": next_time,
            "groups": next_result,
        },
    }
