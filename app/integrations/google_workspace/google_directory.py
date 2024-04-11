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

    Args:
        user_key (str): The user's primary email address, alias email address, or unique user ID.

    Returns:
        dict: A user object.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/get
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

    Returns:
        list: A list of user objects.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/list
    """

    scopes = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]
    service = get_google_service(
        "admin",
        "directory_v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    page_token = None
    all_users = []
    while True:
        results = (
            service.users()
            .list(
                customer=GOOGLE_WORKSPACE_CUSTOMER_ID,
                maxResults=500,
                orderBy="email",
                pageToken=page_token,
            )
            .execute()
        )
        all_users.extend(results.get("users", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return all_users


@handle_google_api_errors
def list_groups():
    """List all groups in the Google Workspace domain.

    Returns:
        list: A list of group objects.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/groups/list
    """

    scopes = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]

    service = get_google_service(
        "admin",
        "directory_v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    all_groups = []
    page_token = None

    while True:
        results = (
            service.groups()
            .list(
                customer=GOOGLE_WORKSPACE_CUSTOMER_ID,
                maxResults=500,
                orderBy="email",
                pageToken=page_token,
            )
            .execute()
        )
        all_groups.extend(results.get("groups", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break

    return all_groups


@handle_google_api_errors
def list_group_members(group_key):
    """List all group members in the Google Workspace domain.

    Returns:
        list: A list of group member objects.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/members/list
    """

    scopes = ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"]

    service = get_google_service(
        "admin",
        "directory_v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    all_group_members = []
    page_token = None

    while True:
        results = (
            service.members()
            .list(
                groupKey=group_key,
                maxResults=500,
                pageToken=page_token,
            )
            .execute()
        )
        all_group_members.extend(results.get("members", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break

    return all_group_members


@handle_google_api_errors
def get_group(group_key):
    """Get a group by group ID in the Google Workspace domain.

    Args:
        group_key (str): The group's email address, group alias, or the unique group ID.

    Returns:
        dict: A group object.
    """
    scopes = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]

    service = get_google_service(
        "admin",
        "directory_v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    group = service.groups().get(groupKey=group_key).execute()
    return group


@handle_google_api_errors
def list_google_cloud_groups():
    scopes = ["https://www.googleapis.com/auth/cloud-identity.groups.readonly"]

    service = get_google_service(
        "cloudidentity",
        "v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    all_groups = []
    page_token = None

    while True:
        results = (
            service.groups()
            .list(
                parent=f"customers/{GOOGLE_WORKSPACE_CUSTOMER_ID}",
                pageToken=page_token,
            )
            .execute()
        )
        all_groups.extend(results.get("groups", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break

    return all_groups


@handle_google_api_errors
def get_google_cloud_group(group_name):
    scopes = ["https://www.googleapis.com/auth/cloud-identity.groups.readonly"]

    service = get_google_service(
        "cloudidentity",
        "v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    group = service.groups().get(name=group_name).execute()
    return group


@handle_google_api_errors
def get_org_unit(org_unit_path):
    scopes = ["https://www.googleapis.com/auth/admin.directory.orgunit.readonly"]

    service = get_google_service(
        "admin",
        "directory_v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    org_unit = (
        service.orgunits()
        .get(customerId=GOOGLE_WORKSPACE_CUSTOMER_ID, orgUnitPath=org_unit_path)
        .execute()
    )
    return org_unit


@handle_google_api_errors
def list_org_units():
    scopes = ["https://www.googleapis.com/auth/admin.directory.orgunit.readonly"]

    service = get_google_service(
        "admin",
        "directory_v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    org_units = (
        service.orgunits().list(customerId=GOOGLE_WORKSPACE_CUSTOMER_ID).execute()
    )
    return org_units
