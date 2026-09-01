"""Google Directory module to interact with the Google Workspace Directory API."""

from typing import Any

import structlog

from infrastructure.configuration.integrations.google import get_google_workspace_settings
from integrations.google_workspace import client as google_service_client
from integrations.utils.api import retry_request
from utils import filters

GOOGLE_WORKSPACE_CUSTOMER_ID = get_google_workspace_settings().GOOGLE_WORKSPACE_CUSTOMER_ID
DIRECTORY_USER_READONLY_SCOPES = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]
DIRECTORY_GROUP_READONLY_SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]

_USERS_PAGE_SIZE = 500
_GROUPS_PAGE_SIZE = 200
_MEMBERS_PAGE_SIZE = 200

logger = structlog.get_logger()


def _collect_pages(resource: Any, request: Any, response_key: str) -> list[dict]:
    """Aggregate every page of an already-built Directory list request.

    Takes the built request rather than call parameters so the ``list(...)``
    call itself stays type-checked against the stub at each call site.
    """
    items: list[dict] = []
    while request is not None:
        response = google_service_client.execute_google_api_request(request)
        items.extend(response.get(response_key, []))
        request = resource.list_next(request, response)
    return items


def list_users(
    customer: str | None = None,
    query: str | None = None,
    fields: str | None = None,
    delegated_user_email: str | None = None,
) -> list[dict]:
    """List all users in the Google Workspace domain.

    Args:
        customer: The unique ID for the Google Workspace customer. Defaults to
            the configured customer ID.
        query: Directory API query filtering the results.
        fields: Partial-response projection, e.g. ``users(primaryEmail, name)``.
        delegated_user_email: Account to impersonate for this call.

    Returns:
        list: A list of user objects.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/list
    """
    users = google_service_client.get_admin_directory_service(
        scopes=DIRECTORY_USER_READONLY_SCOPES,
        delegated_user_email=delegated_user_email,
    ).users()
    request = users.list(
        customer=customer or GOOGLE_WORKSPACE_CUSTOMER_ID,
        maxResults=_USERS_PAGE_SIZE,
        orderBy="email",
        query=query,
        fields=fields,
    )
    return _collect_pages(users, request, "users")


def list_groups(
    customer: str | None = None,
    query: str | None = None,
    fields: str | None = None,
    delegated_user_email: str | None = None,
) -> list[dict]:
    """List all groups in the Google Workspace domain.

    Args:
        customer: The unique ID for the Google Workspace customer. Defaults to
            the configured customer ID.
        query: Directory API query filtering the results, e.g.
            ``email:prefix-*`` for all groups whose email starts with ``prefix-``.
        fields: Partial-response projection, e.g. ``groups(email, name)``.
        delegated_user_email: Account to impersonate for this call.

    Returns:
        list: A list of group objects.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/groups/list
    """
    groups = google_service_client.get_admin_directory_service(
        scopes=DIRECTORY_GROUP_READONLY_SCOPES,
        delegated_user_email=delegated_user_email,
    ).groups()
    request = groups.list(
        customer=customer or GOOGLE_WORKSPACE_CUSTOMER_ID,
        maxResults=_GROUPS_PAGE_SIZE,
        orderBy="email",
        query=query,
        fields=fields,
    )
    return _collect_pages(groups, request, "groups")


def list_group_members(
    group_key: str,
    fields: str | None = None,
    delegated_user_email: str | None = None,
) -> list[dict]:
    """List all members of a Google Workspace group.

    Args:
        group_key: The group's email address or unique group ID.
        fields: Partial-response projection, e.g. ``members(email, role)``.
        delegated_user_email: Account to impersonate for this call.

    Returns:
        list: A list of group member objects.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/members/list
    """
    members = google_service_client.get_admin_directory_service(
        scopes=DIRECTORY_GROUP_READONLY_SCOPES,
        delegated_user_email=delegated_user_email,
    ).members()
    request = members.list(
        groupKey=group_key,
        maxResults=_MEMBERS_PAGE_SIZE,
        fields=fields,
    )
    return _collect_pages(members, request, "members")


def list_groups_with_members(
    groups_filters: list | None = None,
    query: str | None = None,
    tolerate_errors: bool = False,
):
    """List all groups in the Google Workspace domain with their members.

    Args:
        groups_filters (list): List of filters to apply to the groups.
        query (str): The query to search for groups.
        tolerate_errors (bool): Whether to include groups that encountered errors during member detail retrieval.

    Returns:
        list: A list of group objects with members. Any group without members will not be included.
    """
    logger.info("listing_groups_with_members", query=query, groups_filters=groups_filters)
    groups = list_groups(query=query, fields="groups(email, name, directMembersCount, description)")
    logger.info("groups_found", count=len(groups), query=query)

    if not groups:
        return []

    if groups_filters is not None:
        for groups_filter in groups_filters:
            groups = filters.filter_by_condition(groups, groups_filter)
        logger.info("groups_filtered", count=len(groups), groups_filters=groups_filters)

    users = list_users()
    filtered_groups = [
        {k: v for k, v in group.items() if k in ["id", "email", "name", "directMembersCount", "description"]} for group in groups
    ]

    groups_with_members = []
    for group in filtered_groups:
        group_email = group.get("email", "unknown")
        logger.info("getting_members_for_group", group_email=group_email)
        try:
            members = retry_request(
                list_group_members,
                group_email,
                max_attempts=3,
                delay=1,
                fields="members(email, role, type, status)",
            )
        except Exception as e:
            error_message = str(e)
            logger.warning(
                "error_getting_group_members",
                group_email=group_email,
                error=error_message,
            )
            continue

        members = get_members_details(members, users, tolerate_errors)
        if members:
            group.update({"members": members})
            groups_with_members.append(group)
    logger.info("groups_with_members_listed", count=len(groups_with_members))

    return groups_with_members


def get_members_details(members: list[dict], users: list[dict], tolerate_errors=False):
    """Get user details for a list of members.

    Args:
        members (list): A list of member objects.
        users (list): A list of user objects.
        tolerate_errors (bool): Whether to tolerate errors when getting user details.

    Returns:"""

    error_occured = False
    for member in members:
        logger.debug("getting_user_details", member=member)
        user_details = None
        try:
            user_details = next(
                (user for user in users if user["primaryEmail"] == member["email"]),
                None,
            )
            if not user_details:
                raise ValueError("User details not found.")
        except Exception as e:
            logger.warning(
                "getting_user_details_error",
                member=member,
                error=str(e),
            )
            error_occured = True
            if not tolerate_errors:
                break
        if user_details:
            member.update(user_details)
    return members if not error_occured or tolerate_errors else []
