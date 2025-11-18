"""
Google Directory module using simplified Google service functions.

"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

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


@dataclass
class ListGroupsWithMembersRequest:
    """Configuration for list_groups_with_members operation.

    Attributes:
        groups_filters: List of callables(group: dict) -> bool
                       Group is included if it matches ALL filters
        member_filters: List of callables(member: dict) -> bool
                       Group is included if it has AT LEAST ONE member matching ALL filters
        groups_kwargs: Additional kwargs for list_groups API call
        members_kwargs: Additional kwargs for get_batch_group_members API call
        users_kwargs: Additional kwargs for get_batch_users API call
        include_users_details: Whether to fetch and include user details for members
        exclude_empty_groups: Whether to exclude groups with no members
    """

    groups_filters: Optional[List[Callable]] = None
    member_filters: Optional[List[Callable]] = None
    groups_kwargs: Optional[Dict] = field(default_factory=dict)
    members_kwargs: Optional[Dict] = field(default_factory=dict)
    users_kwargs: Optional[Dict] = field(default_factory=dict)
    include_users_details: bool = True
    exclude_empty_groups: bool = False


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

    Args:
        **kwargs: Additional parameters for the API call. For the Google Directory API,
            the 'fields' parameter must use the resource-wrapped format.
            E.g., fields="users(name,primaryEmail)" not fields="name,primaryEmail".

    Returns:
        IntegrationResponse.

    Example:
        result = list_users(fields="users(name,primaryEmail,email)")
        if result.success:
            users = result.data
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

    Args:
        **kwargs: Additional parameters for the API call. For the Google Directory API,
            the 'fields' parameter must use the resource-wrapped format.
            E.g., fields="groups(email,name)" not fields="email,name".
            Can also filter by member: query="memberKey:user@example.com"
            or by email pattern: query="email:prefix*"

    Returns:
        IntegrationResponse.

    Example:
        result = list_groups(fields="groups(email,name,description)")
        result = list_groups(query="memberKey:user@example.com")
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
            For the Google Directory API, the 'fields' parameter must use the
            resource-wrapped format. E.g., fields="members(email,role)"
            not fields="email,role".

    Returns:
        IntegrationResponse: The result of the list operation. On success,
        ``data`` contains the list of members.

    Example:
        result = list_members("group@example.com", fields="members(email,role)")
        if result.success:
            members = result.data
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
    exclude_empty_groups: Optional[bool] = False,
) -> List[dict]:
    """Assemble groups with their members.

    This is a pure assembly function that combines group data with member data.
    No enrichment or filtering - just structural assembly.

    Args:
        groups_list: List of group objects from API
        members_by_group: Dict mapping group key -> list of member objects
        exclude_empty_groups: Whether to exclude groups with no members

    Returns:
        List of groups with members assembled
    """
    results: List[dict] = []
    for g in groups_list:
        if not isinstance(g, dict):
            continue
        key = g.get("email") or g.get("id")
        if not key:
            continue

        members = members_by_group.get(key, [])

        # Check if we should exclude empty groups
        if not members and exclude_empty_groups:
            continue

        g_copy = dict(g)
        g_copy["members"] = [dict(m) for m in members if isinstance(m, dict)]
        results.append(g_copy)

    return results


def _enrich_members_with_users(
    groups_with_members: List[dict],
    users_by_email: Dict[str, dict],
) -> List[dict]:
    """Enrich group members with user details.

    Takes already-assembled groups with members and adds user enrichment.

    Args:
        groups_with_members: Groups with members already assembled
        users_by_email: Dict mapping email -> enriched user object

    Returns:
        Groups with enriched members
    """
    results: List[dict] = []
    for group in groups_with_members:
        if not isinstance(group, dict):
            continue

        enriched_members = []
        for member in group.get("members", []):
            if not isinstance(member, dict):
                continue

            member_copy = dict(member)
            email = member.get("email")

            if email and email in users_by_email:
                user = users_by_email[email]
                if user and isinstance(user, dict) and user.get("primaryEmail"):
                    member_copy["user"] = user
                    # backward-compat: flatten certain fields
                    for k, v in user.items():
                        if k not in member_copy:
                            member_copy[k] = v

            enriched_members.append(member_copy)

        group_copy = dict(group)
        group_copy["members"] = enriched_members
        results.append(group_copy)

    return results


def _filter_groups_by_members(
    groups_with_members: List[dict],
    member_filters: Optional[List] = None,
) -> List[dict]:
    """Filter groups based on member criteria.

    A group is included if it has AT LEAST ONE member matching ALL filter criteria.
    The group is returned WITH ALL its members intact (filtering is on group inclusion,
    not member limitation).

    Examples:
    - Filter for groups that have a MANAGER/OWNER:
      [lambda m: m.get("role") in ["MANAGER", "OWNER"]]
      Result: Only groups with at least one manager/owner (all members included)

    - Filter for groups containing john@example.com:
      [lambda m: m.get("email") == "john@example.com"]
      Result: Only groups that have john (all his roles and all other members included)

    - Filter for groups where john@example.com is a MANAGER/OWNER:
      [
        lambda m: m.get("email") == "john@example.com",
        lambda m: m.get("role") in ["MANAGER", "OWNER"]
      ]
      Result: Only groups where john is manager/owner (all members included)

    Args:
        groups_with_members: Groups with all members already assembled
        member_filters: List of callables(member: dict) -> bool
                       Group is included if ANY member matches ALL filters

    Returns:
        Filtered groups (with all their members intact)
    """
    if not member_filters:
        return groups_with_members

    filtered_groups = []
    for group in groups_with_members:
        if not isinstance(group, dict):
            continue

        members = group.get("members", [])

        # Check if ANY member matches ALL filter criteria
        has_matching_member = any(
            all(f(m) for f in member_filters) for m in members if isinstance(m, dict)
        )

        if has_matching_member:
            filtered_groups.append(group)

    return filtered_groups


def list_groups_with_members(
    request: Optional[ListGroupsWithMembersRequest] = None,
) -> IntegrationResponse:
    """List groups with members, optionally filtered at group and member levels.

    Args:
        request: ListGroupsWithMembersRequest configuration object.
                If None, uses defaults (all groups, all members, with user details).

    Returns:
        IntegrationResponse with list of groups and their members

    Example:
        # List all groups with their members
        result = list_groups_with_members()

        # List groups with email starting with 'team-' and their members
        result = list_groups_with_members(
            ListGroupsWithMembersRequest(
                groups_filters=[lambda g: g.get("email", "").startswith("team-")]
            )
        )
    """
    if request is None:
        request = ListGroupsWithMembersRequest()

    logger.info(
        "listing_groups_with_members",
        request=request,
    )

    # Get groups - google_service_next handles all error cases
    groups_resp = list_groups(**(request.groups_kwargs or {}))
    if not groups_resp.success:
        return groups_resp

    # Apply filters and early return if empty
    groups_list = groups_resp.data or []
    if request.groups_filters:
        groups_list = [
            g for g in groups_list if all(f(g) for f in request.groups_filters)
        ]

    if not groups_list:
        return build_error_response(
            error=Exception("No groups found for filters"),
            function_name="list_groups_with_members",
            integration_name="google",
        )

    # Get members for all groups - google_service_next handles all error cases
    group_keys = [g.get("email") for g in groups_list]
    members_resp = get_batch_group_members(group_keys, **(request.members_kwargs or {}))
    if not members_resp.success:
        return members_resp
    members_by_group: Dict[str, List[dict]] = (
        members_resp.data
        if isinstance(members_resp.data, dict)
        else {k: [] for k in group_keys}
    )
    # Assemble groups with members
    results = _assemble_groups_with_members(
        groups_list, members_by_group, request.exclude_empty_groups
    )
    # Filter groups based on member criteria
    if request.member_filters:
        results = _filter_groups_by_members(results, request.member_filters)

    # Fetch users details if requested
    if request.include_users_details and results:
        member_emails = {
            email
            for group in results
            for m in group.get("members", [])
            if isinstance(m, dict) and (email := m.get("email")) is not None
        }
        if member_emails:
            users_resp = get_batch_users(
                list(member_emails), **(request.users_kwargs or {})
            )
            if users_resp.success:
                users_by_email = users_resp.data or {}
            else:
                users_by_email = {}
            results = _enrich_members_with_users(results, users_by_email)

    return build_success_response(results, "list_groups_with_members", "google")
