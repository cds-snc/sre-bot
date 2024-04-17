"""Google Directory module to interact with the Google Workspace Directory API."""

from integrations.google_workspace.google_service import (
    handle_google_api_errors,
    execute_google_api_call,
    DEFAULT_DELEGATED_ADMIN_EMAIL,
    DEFAULT_GOOGLE_WORKSPACE_CUSTOMER_ID,
)


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
        maxResults=10,
        orderBy="email",
    )


@handle_google_api_errors
def list_groups(
    delegated_user_email=None,
    customer=None,
):
    """List all groups in the Google Workspace domain.

    Returns:
        list: A list of group objects.

    Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/groups/list
    """
    if not delegated_user_email:
        delegated_user_email = DEFAULT_DELEGATED_ADMIN_EMAIL
    if not customer:
        customer = DEFAULT_GOOGLE_WORKSPACE_CUSTOMER_ID
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
        maxResults=100,
        orderBy="email",
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
    )
