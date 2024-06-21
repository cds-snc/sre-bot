"""Google Directory module to interact with the Google Workspace Directory API."""

from integrations.google_workspace.google_service import (
    handle_google_api_errors,
    execute_google_api_call,
    DEFAULT_DELEGATED_ADMIN_EMAIL,
    DEFAULT_GOOGLE_WORKSPACE_CUSTOMER_ID,
)
from integrations.utils.api import convert_string_to_camel_case
from utils import filters


@handle_google_api_errors
def get_user(user_key, delegated_user_email=None):
    """Get a user by user key in the Google Workspace domain.

    Args:
        user_key (str): The user's primary email address, alias email address, or unique user ID.
        delegated_user_email (str): The email address of the user to impersonate. (default: must be defined in .env)

    Returns:
        dict: A user object.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/get
    """

    if not delegated_user_email:
        delegated_user_email = DEFAULT_DELEGATED_ADMIN_EMAIL
    scopes = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "users",
        "get",
        scopes,
        delegated_user_email,
        userKey=user_key,
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
        delegated_user_email = DEFAULT_DELEGATED_ADMIN_EMAIL
    if not customer:
        customer = DEFAULT_GOOGLE_WORKSPACE_CUSTOMER_ID
    scopes = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]
    return execute_google_api_call(
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
        delegated_user_email = DEFAULT_DELEGATED_ADMIN_EMAIL
    if not customer:
        customer = DEFAULT_GOOGLE_WORKSPACE_CUSTOMER_ID

    kwargs = {convert_string_to_camel_case(k): v for k, v in kwargs.items()}
    scopes = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]
    return execute_google_api_call(
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
def list_group_members(group_key, delegated_user_email=None):
    """List all group members in the Google Workspace domain.

    Returns:
        list: A list of group member objects.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/members/list
    """

    if not delegated_user_email:
        delegated_user_email = DEFAULT_DELEGATED_ADMIN_EMAIL
    scopes = ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"]
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "list",
        scopes,
        delegated_user_email,
        paginate=True,
        groupKey=group_key,
        maxResults=200,
    )


@handle_google_api_errors
def get_group(group_key):
    scopes = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]
    return execute_google_api_call(
        "admin",
        "directory_v1",
        "groups",
        "get",
        scopes,
        DEFAULT_DELEGATED_ADMIN_EMAIL,
        groupKey=group_key,
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


def list_groups_with_members(**kwargs):
    """List all groups in the Google Workspace domain with their members.

    Returns:
        list: A list of group objects with members. Any group without members will not be included.
    """
    members_details = kwargs.pop("members_details", True)
    groups = list_groups(**kwargs)
    groups_filters = kwargs.pop("filters", [])
    if not groups:
        return []

    for filter in groups_filters:
        groups = filters.filter_by_condition(groups, filter)

    groups_with_members = []
    for group in groups:
        members = list_group_members(group["email"])
        if members and members_details:
            detailed_members = []
            for member in members:
                detailed_members.append(get_user(member["email"]))
            group["members"] = detailed_members
            groups_with_members.append(group)
    return groups_with_members
