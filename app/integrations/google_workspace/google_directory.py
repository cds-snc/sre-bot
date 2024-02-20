"""Google Directory module for interacting with the Google Workspace Directory API."""

import os
from integrations.google_workspace.google_service import (
    get_google_service,
    handle_google_api_errors,
)

GOOGLE_DELEGATED_ADMIN_EMAIL = os.environ.get("GOOGLE_DELEGATED_ADMIN_EMAIL")


@handle_google_api_errors
def list_users():
    """List all users in the Google Workspace domain.

      reference: https://admin.googleapis.com/admin/directory/v1/users

    Returns:
        list: A list of user objects.
    """

    scopes = [
        "https://www.googleapis.com/auth/admin.directory.user.readonly",
        "https://www.googleapis.com/auth/admin.directory.group.readonly",
        "https://www.googleapis.com/auth/admin.directory.group.member.readonly",
        "https://www.googleapis.com/auth/admin.reports.audit.readonly",
    ]

    service = get_google_service(
        "admin",
        "directory_v1",
        delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,
        scopes=scopes,
    )
    users = (
        service.users()
        .list(customer="C03nmsv71", maxResults=500, orderBy="email")
        .execute()
    )
    return users.get("users", [])
