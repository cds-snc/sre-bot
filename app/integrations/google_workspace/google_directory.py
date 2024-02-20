"""Google Directory module for interacting with the Google Workspace Directory API."""

import os
from integrations.google_workspace.google_service import (
    get_google_service,
    handle_google_api_errors,
)

GOOGLE_DELEGATED_ADMIN_EMAIL = os.environ.get("GOOGLE_DELEGATED_ADMIN_EMAIL")
GOOGLE_WORKSPACE_CUSTOMER_ID = os.environ.get("GOOGLE_WORKSPACE_CUSTOMER_ID")


@handle_google_api_errors
def get_user(user_key):
    """Get a user by user key in the Google Workspace domain.

    reference: https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/get

    Args:
        user_key (str): The user's primary email address, alias email address, or unique user ID.

    Returns:
        dict: A user object.
    """

    scopes = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]

    service = get_google_service(
        "admin",
        "directory_v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    user = service.users().get(userKey=user_key).execute()
    return user


@handle_google_api_errors
def list_users():
    """List all users in the Google Workspace domain.

      reference: https://admin.googleapis.com/admin/directory/v1/users

    Returns:
        list: A list of user objects.
    """

    scopes = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]

    service = get_google_service(
        "admin",
        "directory_v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    users = (
        service.users()
        .list(customer=GOOGLE_WORKSPACE_CUSTOMER_ID, maxResults=500, orderBy="email")
        .execute()
    )
    return users.get("users", [])


@handle_google_api_errors
def list_groups():
    """List all groups in the Google Workspace domain.

    reference: https://admin.googleapis.com/admin/directory/v1/groups

    Returns:
        list: A list of group objects.
    """

    scopes = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]

    service = get_google_service(
        "admin",
        "directory_v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    groups = (
        service.groups()
        .list(customer=GOOGLE_WORKSPACE_CUSTOMER_ID, maxResults=500, orderBy="email")
        .execute()
    )
    return groups.get("groups", [])


@handle_google_api_errors
def list_group_members(group_key):
    """List all group members in the Google Workspace domain.

    reference: https://admin.googleapis.com/admin/directory/v1/members

    Returns:
        list: A list of group member objects.
    """

    scopes = ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"]

    service = get_google_service(
        "admin",
        "directory_v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    group_members = service.members().list(groupKey=group_key, maxResults=500).execute()
    return group_members.get("members", [])
