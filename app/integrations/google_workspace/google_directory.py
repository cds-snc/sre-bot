"""Google Directory module to interact with the Google Workspace Directory API."""

import pandas as pd
from integrations.google_workspace import google_service
from integrations.utils.api import convert_string_to_camel_case, retry_request
from utils import filters
from core.logging import get_module_logger

GOOGLE_DELEGATED_ADMIN_EMAIL = google_service.GOOGLE_DELEGATED_ADMIN_EMAIL
GOOGLE_WORKSPACE_CUSTOMER_ID = google_service.GOOGLE_WORKSPACE_CUSTOMER_ID
logger = get_module_logger()
handle_google_api_errors = google_service.handle_google_api_errors


@handle_google_api_errors
def get_user(user_key, delegated_user_email=None, fields=None):
    """Get a user by user key in the Google Workspace domain.

    Args:
        user_key (str): The user's primary email address, alias email address, or unique user ID.
        delegated_user_email (str): The email address of the user to impersonate. (default: must be defined in .env)

    Returns:
        dict: A user object.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/get
    """

    if not delegated_user_email:
        delegated_user_email = GOOGLE_DELEGATED_ADMIN_EMAIL
    scopes = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]
    return google_service.execute_google_api_call(
        "admin",
        "directory_v1",
        "users",
        "get",
        scopes,
        delegated_user_email,
        userKey=user_key,
        fields=fields,
    )


@handle_google_api_errors
def list_users(
    delegated_user_email=None,
    customer=None,
    **kwargs,
):
    """List all users in the Google Workspace domain.

    Returns:
        list: A list of user objects.
    """
    if not delegated_user_email:
        delegated_user_email = GOOGLE_DELEGATED_ADMIN_EMAIL
    if not customer:
        customer = GOOGLE_WORKSPACE_CUSTOMER_ID
    scopes = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]
    return google_service.execute_google_api_call(
        "admin",
        "directory_v1",
        "users",
        "list",
        scopes,
        delegated_user_email,
        paginate=True,
        customer=customer,
        maxResults=500,
        orderBy="email",
    )


@handle_google_api_errors
def list_groups(
    delegated_user_email=None,
    customer=None,
    **kwargs,
):
    """List all groups in the Google Workspace domain. A query can be provided to filter the results (e.g. query="email:prefix-*" will filter for all groups where the email starts with 'prefix-').

    Returns:
        list: A list of group objects.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/groups/list
    """
    if not delegated_user_email:
        delegated_user_email = GOOGLE_DELEGATED_ADMIN_EMAIL
    if not customer:
        customer = GOOGLE_WORKSPACE_CUSTOMER_ID

    kwargs = {convert_string_to_camel_case(k): v for k, v in kwargs.items()}
    scopes = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]
    return google_service.execute_google_api_call(
        "admin",
        "directory_v1",
        "groups",
        "list",
        scopes,
        delegated_user_email,
        paginate=True,
        customer=customer,
        maxResults=200,
        orderBy="email",
        **kwargs,
    )


@handle_google_api_errors
def list_group_members(group_key, delegated_user_email=None, fields=None):
    """List all group members in the Google Workspace domain.

    Args:
        group_key (str): The group's email address or unique group ID.
        delegated_user_email (str): The email address of the user to impersonate. (default: must be defined in .env)

    Returns:
        list: A list of group member objects.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/members/list
    """

    if not delegated_user_email:
        delegated_user_email = GOOGLE_DELEGATED_ADMIN_EMAIL
    scopes = ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"]
    return google_service.execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "list",
        scopes,
        delegated_user_email,
        paginate=True,
        groupKey=group_key,
        maxResults=200,
        fields=fields,
    )


@handle_google_api_errors
def get_group(group_key, fields=None):
    scopes = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]
    return google_service.execute_google_api_call(
        "admin",
        "directory_v1",
        "groups",
        "get",
        scopes,
        GOOGLE_DELEGATED_ADMIN_EMAIL,
        groupKey=group_key,
        fields=fields,
    )


def add_users_to_group(group, group_key):
    """Add users to a group in the Google Workspace domain.

    Args:
        group_key (str): The group's email address or unique group ID.

    Returns:
        list: A list of user objects.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/members/insert
    """
    result = list_group_members(group_key)
    if result:
        group["members"] = result
    return group


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
    logger.info(
        "listing_groups_with_members", query=query, groups_filters=groups_filters
    )
    groups = list_groups(
        query=query, fields="groups(email, name, directMembersCount, description)"
    )
    logger.info("groups_found", count=len(groups), query=query)

    if not groups:
        return []

    if groups_filters is not None:
        for groups_filter in groups_filters:
            groups = filters.filter_by_condition(groups, groups_filter)
        logger.info("groups_filtered", count=len(groups), groups_filters=groups_filters)

    users = list_users()
    filtered_groups = [
        {
            k: v
            for k, v in group.items()
            if k in ["id", "email", "name", "directMembersCount", "description"]
        }
        for group in groups
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


def convert_google_groups_members_to_dataframe(groups):
    """Converts a list of Google groups with members to a DataFrame.

    Args:
        groups (list): A list of group objects with members.

    Returns:
        DataFrame: A DataFrame with group members.
    """
    flattened_data = []
    for group in groups:
        group_email = group.get("email")
        group_name = group.get("name")
        group_direct_members_count = group.get("directMembersCount")
        group_description = group.get("description")

        for member in group.get("members", []):
            member_email = member.get("email")
            member_role = member.get("role")
            member_type = member.get("type")
            member_status = member.get("status")
            member_primary_email = member.get("primaryEmail")
            member_given_name = member.get("name", {}).get("givenName")
            member_family_name = member.get("name", {}).get("familyName")

            flattened_record = {
                "group_email": group_email,
                "group_name": group_name,
                "group_direct_members_count": group_direct_members_count,
                "group_description": group_description,
                "member_email": member_email,
                "member_role": member_role,
                "member_type": member_type,
                "member_status": member_status,
                "member_primary_email": member_primary_email,
                "member_given_name": member_given_name,
                "member_family_name": member_family_name,
            }
            flattened_data.append(flattened_record)

    return pd.DataFrame(flattened_data)
