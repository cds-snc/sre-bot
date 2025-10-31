"""
Google Directory module using simplified Google service functions.

"""

from typing import Dict, List, Optional

from core.logging import get_module_logger
from integrations.google_workspace import google_service_next as google_service
from integrations.google_workspace.google_service_next import (
    execute_batch_request,
    execute_google_api_call,
    get_google_service,
)
from models.integrations import (
    IntegrationResponse,
    build_success_response,
    build_error_response,
)

GOOGLE_WORKSPACE_CUSTOMER_ID = google_service.GOOGLE_WORKSPACE_CUSTOMER_ID

logger = get_module_logger()


def get_user(user_key: str, **kwargs) -> IntegrationResponse:
    """Get a user from Google Directory.

    Returns an IntegrationResponse.
    """
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "users",
        "get",
        scopes=["https://www.googleapis.com/auth/admin.directory.user.readonly"],
        userKey=user_key,
        **kwargs,
    )


def get_batch_users(user_keys: List[str], **kwargs) -> IntegrationResponse:
    """Get multiple users from Google Directory using batch requests.

    Returns an IntegrationResponse with data = {user_key: user_dict | None}
    """
    logger.debug("get_batch_users", user_keys=user_keys, kwargs=kwargs)
    service = get_google_service(
        "admin",
        "directory_v1",
        scopes=["https://www.googleapis.com/auth/admin.directory.user.readonly"],
    )
    requests = []
    for user_key in user_keys:
        req = service.users().get(userKey=user_key, **kwargs)
        requests.append((user_key, req))

    resp = execute_batch_request(service, requests)
    if not isinstance(resp, IntegrationResponse):
        return build_error_response(
            Exception("invalid batch response"), "get_batch_users", "google"
        )

    if not resp.success:
        return build_error_response(
            Exception(str(resp.error)), "get_batch_users", "google"
        )

    results = resp.data.get("results", {}) if isinstance(resp.data, dict) else {}
    users_by_key: Dict[str, Optional[dict]] = {k: results.get(k) for k in user_keys}
    return build_success_response(users_by_key, "get_batch_users", "google")


def list_users(**kwargs) -> IntegrationResponse:
    """List all users from Google Directory with integrated error handling and auto-pagination.

    Returns an IntegrationResponse.
    """
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "users",
        "list",
        scopes=["https://www.googleapis.com/auth/admin.directory.user.readonly"],
        customer=GOOGLE_WORKSPACE_CUSTOMER_ID,
        **kwargs,
    )


def get_group(group_key: str, **kwargs) -> IntegrationResponse:
    """Get a group from Google Directory with integrated error handling.

    Returns an IntegrationResponse.
    """
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "groups",
        "get",
        scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
        groupKey=group_key,
        **kwargs,
    )


def get_batch_groups(group_keys: List[str], **kwargs) -> IntegrationResponse:
    """Get multiple groups from Google Directory using batch requests.

    Returns an IntegrationResponse with data = {group_key: group_dict | None}
    """
    logger.info("get_batch_groups", group_keys=group_keys, kwargs=kwargs)
    service = get_google_service(
        "admin",
        "directory_v1",
        scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
    )
    requests = []
    for group_key in group_keys:
        req = service.groups().get(groupKey=group_key, **kwargs)
        requests.append((group_key, req))

    resp = execute_batch_request(service, requests)
    if not isinstance(resp, IntegrationResponse):
        return build_error_response(
            Exception("invalid batch response"), "get_batch_groups", "google"
        )

    if not resp.success:
        return build_error_response(
            Exception(str(resp.error)), "get_batch_groups", "google"
        )

    results = resp.data.get("results", {}) if isinstance(resp.data, dict) else {}
    groups_by_key: Dict[str, Optional[dict]] = {k: results.get(k) for k in group_keys}
    return build_success_response(groups_by_key, "get_batch_groups", "google")


def list_groups(**kwargs) -> IntegrationResponse:
    """List all groups from Google Directory with integrated error handling and auto-pagination.

    Note: Can be used to list all groups for a user by passing a query parameter with the memberKey.

    e.g., to list all groups for a user with email user@example.com, you can use:
    ```
    list_groups(query="memberKey:user@example.com")
    list_groups(query="email:prefix*")
    ```

    Returns an IntegrationResponse.
    """
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "groups",
        "list",
        scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
        customer=GOOGLE_WORKSPACE_CUSTOMER_ID,
        **kwargs,
    )


def get_member(group_key: str, member_key: str, **kwargs) -> IntegrationResponse:
    """Get a member of a group from Google Directory with integrated error handling.

    Returns an IntegrationResponse.
    """
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "get",
        scopes=[
            "https://www.googleapis.com/auth/admin.directory.group.member.readonly"
        ],
        groupKey=group_key,
        memberKey=member_key,
        **kwargs,
    )


def get_batch_members_for_user(
    group_keys: List[str], user_key: str, **kwargs
) -> IntegrationResponse:
    """Get multiple groups' member object for a user using batch requests."""
    logger.debug(
        "get_batch_members_for_user",
        group_keys=group_keys,
        user_key=user_key,
        kwargs=kwargs,
    )
    service = get_google_service(
        "admin",
        "directory_v1",
        scopes=[
            "https://www.googleapis.com/auth/admin.directory.group.member.readonly"
        ],
    )
    requests = []
    for group_key in group_keys:
        req = service.members().get(groupKey=group_key, memberKey=user_key, **kwargs)
        requests.append((group_key, req))

    resp = execute_batch_request(service, requests)
    if not isinstance(resp, IntegrationResponse):
        return build_error_response(
            Exception("invalid batch response"), "get_batch_members_for_user", "google"
        )

    if not resp.success:
        return build_error_response(
            Exception(str(resp.error)), "get_batch_members_for_user", "google"
        )

    results = resp.data.get("results", {}) if isinstance(resp.data, dict) else {}
    members_by_group: Dict[str, Optional[dict]] = {
        k: results.get(k) for k in group_keys
    }
    return build_success_response(
        members_by_group, "get_batch_members_for_user", "google"
    )


def get_batch_group_members(group_keys: List[str], **kwargs) -> IntegrationResponse:
    """Get multiple groups' members using batch requests.

    Args:
        group_keys (List[str]): List of group keys to fetch members for.
        **kwargs: Additional keyword arguments for the members.list API call.

    Returns:
        Dict[str, List[dict]]: A dictionary mapping group keys to their members.
    """
    logger.debug("get_batch_group_members", group_keys=group_keys, kwargs=kwargs)
    service = get_google_service(
        "admin",
        "directory_v1",
        scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
    )
    requests = []
    for group_key in group_keys:
        req = service.members().list(groupKey=group_key, **kwargs)
        requests.append((group_key, req))

    resp = execute_batch_request(service, requests)
    if not isinstance(resp, IntegrationResponse):
        return build_error_response(
            Exception("invalid batch response"), "get_batch_group_members", "google"
        )

    if not resp.success:
        return build_error_response(
            Exception(str(resp.error)), "get_batch_group_members", "google"
        )

    results = resp.data.get("results", {}) if isinstance(resp.data, dict) else {}
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

    return build_success_response(members_by_group, "get_batch_group_members", "google")


def list_members(group_key: str, **kwargs) -> IntegrationResponse:
    """List all members of a group from Google Directory.

    This uses the simplified Google service functions which handle error
    reporting and auto-pagination.

    Args:
        group_key: The group's email address or unique id.
        **kwargs: Additional keyword arguments forwarded to the underlying API call.

    Returns:
        IntegrationResponse: The result of the list operation. On success,
        ``data`` contains the list of members.
    """
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "list",
        scopes=["https://www.googleapis.com/auth/admin.directory.group.readonly"],
        groupKey=group_key,
        **kwargs,
    )


def has_member(group_key: str, member_key: str, **kwargs) -> IntegrationResponse:
    """Check if a member exists in a group with integrated error handling.

    Returns an IntegrationResponse whose data is truthy/falsey indicating membership.
    """
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "hasMember",
        scopes=[
            "https://www.googleapis.com/auth/admin.directory.group.member.readonly"
        ],
        groupKey=group_key,
        memberKey=member_key,
        **kwargs,
    )


def insert_member(
    group_key: str,
    email: str,
    role: str = "MEMBER",
    type_: str = "USER",
    member_body: Optional[dict] = None,
    **kwargs,
) -> IntegrationResponse:
    """
    Inserts a member into the specified Google Workspace group. If
    ``member_body`` is provided it overrides ``email``, ``role``, and
    ``type_``.

    Args:
        group_key: The group's email address or unique id.
        email: The member's email address.
        role: Role for the new member (for example, "MEMBER", "OWNER", "MANAGER").
        type_: The member type (for example, "USER", "GROUP", "CUSTOMER", "DOMAIN").
        member_body: Optional dictionary representing the member resource. If
            provided, this object is sent as the request body and takes precedence
            over ``email``, ``role``, and ``type_``.
        **kwargs: Additional keyword arguments forwarded to the underlying API call.

    Returns:
        IntegrationResponse: The result of the insert operation. On success,
        ``data`` contains the inserted member resource.
    """
    if member_body is None:
        member_body = {"email": email, "role": role, "type": type_}

    # delegate error handling to execute_google_api_call (google_service_next)
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "insert",
        scopes=["https://www.googleapis.com/auth/admin.directory.group"],
        groupKey=group_key,
        body=member_body,
        **kwargs,
    )


def delete_member(group_key: str, member_key: str) -> IntegrationResponse:
    """Delete a member from a Google Workspace group.

    Args:
        group_key: The group's email address or unique id.
        member_key: The member's email address or unique id.

    Returns:
        IntegrationResponse: The result of the delete operation. On success,
        ``data`` is typically None.
    """
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "delete",
        scopes=["https://www.googleapis.com/auth/admin.directory.group"],
        groupKey=group_key,
        memberKey=member_key,
    )


def _assemble_groups_with_members(
    groups_list: List[dict],
    members_by_group: Dict[str, List[dict]],
    users_by_email: Dict[str, dict],
    members_kwargs: Optional[dict],
) -> List[dict]:
    results: List[dict] = []
    for g in groups_list:
        if not isinstance(g, dict):
            continue
        key = g.get("email") or g.get("id")
        if not key:
            continue
        members = members_by_group.get(key, [])
        enriched_members: List[dict] = []
        for m in members:
            if not isinstance(m, dict):
                continue
            member_copy = dict(m)
            email = m.get("email")
            if email:
                user = users_by_email.get(email)
                if user and isinstance(user, dict) and user.get("primaryEmail"):
                    member_copy["user"] = user
                    # backward-compat: flatten certain fields
                    for k, v in user.items():
                        if k not in member_copy:
                            member_copy[k] = v
            enriched_members.append(member_copy)

        if (
            not enriched_members
            and members_kwargs
            and members_kwargs.get("exclude_empty_groups")
        ):
            continue

        g_copy = dict(g)
        g_copy["members"] = enriched_members
        results.append(g_copy)
    return results


def list_groups_with_members(
    groups_filters: Optional[list] = None,
    users_filters: Optional[list] = None,
    groups_kwargs: Optional[dict] = None,
    members_kwargs: Optional[dict] = None,
    users_kwargs: Optional[dict] = None,
) -> IntegrationResponse:
    """
    List all groups in the Google Workspace domain with their members.

    Returns an IntegrationResponse whose data is a list of groups with an added
    "members" key containing the group's members (possibly enriched with user details).
    """
    logger.info(
        "listing_groups_with_members",
        groups_kwargs=groups_kwargs,
        members_kwargs=members_kwargs,
        users_kwargs=users_kwargs,
        groups_filters=groups_filters,
        users_filters=users_filters,
    )

    # Get groups - google_service_next handles all error cases
    groups_resp = list_groups(**(groups_kwargs or {}))
    if not groups_resp.success:
        return groups_resp

    # Apply filters and early return if empty
    groups_list = groups_resp.data or []
    if groups_filters:
        groups_list = [g for g in groups_list if all(f(g) for f in groups_filters)]

    if not groups_list:
        return build_error_response(
            error=Exception("No groups found for filters"),
            function_name="list_groups_with_members",
            integration_name="google",
        )
    # Get members for all groups - google_service_next handles all error cases
    group_keys = [g.get("email") for g in groups_list]
    members_resp = get_batch_group_members(group_keys, **(members_kwargs or {}))
    if not members_resp.success:
        return members_resp
    members_by_group: Dict[str, List[dict]] = (
        members_resp.data
        if isinstance(members_resp.data, dict)
        else {k: [] for k in group_keys}
    )
    # Collect member emails and fetch user details - google_service_next handles all error cases
    member_emails = {
        email
        for members in members_by_group.values()
        for m in members
        if isinstance(m, dict) and (email := m.get("email")) is not None
    }

    users_by_email: Dict[str, dict] = {}
    if users_filters:

        def user_filter(user: dict) -> bool:
            return all(f(user) for f in users_filters)

    if member_emails:
        users_resp = get_batch_users(list(member_emails), **(users_kwargs or {}))
        if users_resp.success:
            users_by_email = users_resp.data or {}

    # Assemble final results
    results = _assemble_groups_with_members(
        groups_list, members_by_group, users_by_email, members_kwargs
    )
    return build_success_response(results, "list_groups_with_members", "google")
