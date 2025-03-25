"""Google Workspace Directory API methods."""

from googleapiclient.discovery import Resource  # type: ignore
from integrations.google_next.service import (
    execute_google_api_call,
    handle_google_api_errors,
    get_google_service,
    GOOGLE_DELEGATED_ADMIN_EMAIL,
    GOOGLE_WORKSPACE_CUSTOMER_ID,
)

# from integrations.google_next import service as google_service
from integrations.utils.api import retry_request
from utils import filters
from core.logging import get_module_logger


logger = get_module_logger()


class GoogleDirectory:
    """
    A class to simplify the use of various Google Directory API operations across modules.

    This class provides methods to interact with the Google Workspace Directory API, including
    operations for users, groups, and group members. It handles authentication and API calls,
    and includes error handling for Google API errors.

    While this class aims to simplify the usage of the Google Directory API, it is always possible
    to use the Google API Python client directly as per the official documentation:
    (https://googleapis.github.io/google-api-python-client/docs/)

    Attributes:
        scopes (list): The list of scopes to request.
        delegated_email (str): The email address of the user to impersonate.
        service (Resource): Optional - An authenticated Google service resource. If provided, the service will be used instead of creating a new one.
    """

    def __init__(
        self, scopes=None, delegated_email=None, service: Resource | None = None
    ):
        if not scopes and not service:
            raise ValueError("Either scopes or a service must be provided.")
        if not delegated_email and not service:
            delegated_email = GOOGLE_DELEGATED_ADMIN_EMAIL
        self.scopes = scopes
        self.delegated_email = delegated_email
        self.service = service if service else self._get_directory_service()
        logger.debug(
            "google_directory_initialized",
            scopes=scopes,
            delegated_email=delegated_email,
        )

    def _get_directory_service(self) -> Resource:
        """Get authenticated directory service for Google Workspace."""
        logger.debug(
            "getting_directory_service",
            scopes=self.scopes,
            delegated_email=self.delegated_email,
        )
        return get_google_service(
            "admin", "directory_v1", self.scopes, self.delegated_email
        )

    @handle_google_api_errors
    def get_user(self, user_key, **kwargs):
        """Get a user by user key in the Google Workspace domain.

        Args:
            service (Resource): An authenticated Google service resource.
            user_key (str): The user's primary email address, alias email address, or unique user ID.
            kwargs: Additional keyword arguments to pass to. See the reference for more information.

        Returns:
            dict: A user object.

        Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/get
        """
        logger.debug("getting_user", user_key=user_key, kwargs=kwargs)
        return execute_google_api_call(
            self.service, "users", "get", userKey=user_key, **kwargs
        )

    @handle_google_api_errors
    def list_users(
        self,
        customer: str | None = None,
        **kwargs,
    ) -> list[dict]:
        """List all users in the Google Workspace domain.

        Args:
            service (Resource): An authenticated Google service resource.
            customer (str): The unique ID for the customer's Google Workspace account. (default: GOOGLE_WORKSPACE_CUSTOMER_ID)
            orderBy (str): The attribute to use for ordering the results. (default: "email")
            kwargs: Additional keyword arguments to pass to. See the reference for more information.

        Returns:
            list: A list of user objects.

        Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/list
        """
        logger.debug("listing_users", customer=customer, kwargs=kwargs)
        if not customer:
            customer = GOOGLE_WORKSPACE_CUSTOMER_ID

        return execute_google_api_call(
            self.service,
            "users",
            "list",
            paginate=True,
            customer=customer,
            **kwargs,
        )

    # Groups methods
    @handle_google_api_errors
    def get_group(self, group_key: str, **kwargs):
        """Get a group by group key in the Google Workspace domain.

        Args:
            service (Resource): An authenticated Google service resource.
            group_key (str): The group's email address or unique group ID.
            kwargs: Additional keyword arguments to pass to. See the reference for more information.

        Returns:
            dict: A group object.

        Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/groups/get
        """
        logger.debug("getting_group", group_key=group_key, kwargs=kwargs)

        return execute_google_api_call(
            self.service, "groups", "get", groupKey=group_key, **kwargs
        )

    @handle_google_api_errors
    def list_groups(
        self,
        customer: str | None = None,
        **kwargs,
    ) -> list[dict]:
        """List all groups in the Google Workspace domain. A query can be provided to filter the results (e.g. query="email:prefix-*" will filter for all groups where the email starts with 'prefix-').

        Args:
            service (Resource): An authenticated Google service resource.
            customer (str): The unique ID for the customer's Google Workspace account. (default: GOOGLE_WORKSPACE_CUSTOMER_ID)
            kwargs: Additional keyword arguments to pass to. See the reference for more information.
        Returns:
            list: A list of group objects.

        Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/groups/list
        """
        logger.debug("listing_groups", customer=customer, kwargs=kwargs)

        if not customer:
            customer = GOOGLE_WORKSPACE_CUSTOMER_ID
        return execute_google_api_call(
            self.service,
            "groups",
            "list",
            paginate=True,
            customer=customer,
            **kwargs,
        )

    # Group members methods
    @handle_google_api_errors
    def list_group_members(self, group_key: str, **kwargs):
        """List all group members in the Google Workspace domain.

        Args:
            service (Resource): An authenticated Google service resource
            group_key (str): The group's email address or unique group ID.
            delegated_user_email (str): The email address of the user to impersonate. (default: must be defined in .env)

        Returns:
            list: A list of group member objects.

        Ref: https://developers.google.com/admin-sdk/directory/reference/rest/v1/members/list
        """
        logger.debug("listing_group_members", group_key=group_key, kwargs=kwargs)

        return execute_google_api_call(
            self.service,
            "members",
            "list",
            paginate=True,
            groupKey=group_key,
            **kwargs,
        )

    def list_groups_with_members(
        self,
        query: str | None = None,
        groups_filters: list | None = None,
    ):
        """List all groups in the Google Workspace domain with their members and their details.

        Args:
            service (Resource): An authenticated Google service resource.
            query (str): A query to filter the groups. (default: None)
            groups_filters (list): A list of filters to apply to the groups. (default: [])

        Returns:
            list: A list of group objects with members and their details.
        """
        logger.info(
            "listing_groups_with_members", query=query, groups_filters=groups_filters
        )

        groups: list[dict] = self.list_groups(
            query=query,
            fields="groups(email, name, directMembersCount, description)",
        )
        logger.info("groups_found", count=len(groups), query=query)

        if len(groups) == 0:
            return []

        users: list[dict] = self.list_users()

        if groups_filters is not None:
            for groups_filter in groups_filters:
                groups = filters.filter_by_condition(groups, groups_filter)
            logger.info(
                "groups_filtered", count=len(groups), groups_filters=groups_filters
            )

        groups_with_members = []

        for group in groups:
            group_email = group.get("email", "unknown")
            logger.info("getting_members_for_group", group_email=group_email)

            try:
                members = retry_request(
                    self.list_group_members,
                    group["email"],
                    max_attempts=3,
                    delay=1,
                    fields="members(email, role, type, status)",
                )
            except Exception as e:
                error_message = str(e)
                group["error"] = f"Error getting members: {error_message}"
                logger.warning(
                    "error_getting_group_members",
                    group_email=group_email,
                    error=error_message,
                )
                continue
            members = self.get_members_details(members, users)
            if members:
                group.update({"members": members})
                if any(member.get("error") for member in members) and not group.get(
                    "error"
                ):
                    group["error"] = "Error getting members details."
                groups_with_members.append(group)
        logger.info("groups_with_members_listed", count=len(groups_with_members))
        return groups_with_members

    def get_members_details(self, members: list[dict], users: list[dict]):
        """Get user details for a list of members.

        Args:
            members (list): A list of member objects.
            tolerate_errors (bool): Whether to tolerate errors when getting user details.

        Returns:
            list: A list of member objects with user details.
        """

        for member in members:
            member_email = member.get("email", "unknown")
            logger.debug("getting_user_details_for_member", member_email=member_email)
            user_details = next(
                (user for user in users if user["primaryEmail"] == member["email"]),
                None,
            )
            if user_details:
                member.update(user_details)
                logger.debug("user_details_found", member_email=member_email)

            else:
                member["error"] = "User details not found"
                logger.warning("user_details_not_found", member_email=member_email)

        return members
