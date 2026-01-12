"""Test module for new Google Workspace infrastructure client.

Simple test to verify the new DirectoryClient works correctly.
Will be removed once verified - not part of production code.
"""

import structlog
from structlog.stdlib import BoundLogger

from infrastructure.services import get_google_workspace_clients
from infrastructure.clients.google_workspace import ListGroupsWithMembersRequest

logger: BoundLogger = structlog.get_logger()


def test_get_user() -> None:
    """Test retrieving a single user from Google Workspace Directory API.

    Edit the USER_EMAIL below to test different users.
    """
    # ============ EDIT THIS TO TEST DIFFERENT USERS ============
    USER_EMAIL = "user@example.com"
    # ===========================================================

    log = logger.bind(test="get_user", user_email=USER_EMAIL)
    log.info("starting_user_retrieval_test")

    try:
        # Get Google Workspace clients from service provider
        google_clients = get_google_workspace_clients()

        log.info("initialized_google_clients")

        # Retrieve the user
        result = google_clients.directory.get_user(USER_EMAIL)

        # Handle the result
        if result.is_success:
            user = result.data if result.data else {}
            log.info(
                "user_retrieved_successfully",
                primary_email=user.get("primaryEmail"),
                full_name=user.get("name", {}).get("fullName"),
                status=user.get("suspended", False),
            )
            return

        # Handle different error statuses
        log.error(
            "failed_to_retrieve_user",
            status=result.status,
            message=result.message,
            error_code=result.error_code,
        )

    except Exception as e:
        log.error("test_exception", error=str(e), exc_info=True)


def test_list_groups() -> None:
    """Test listing groups from Google Workspace Directory API."""
    log = logger.bind(test="list_groups")
    log.info("starting_group_listing_test")

    try:
        # Get Google Workspace clients from service provider
        google_clients = get_google_workspace_clients()

        log.info("initialized_google_clients")

        # List the groups
        result = google_clients.directory.list_groups(query="email:aws-*")

        # Handle the result
        if result.is_success:
            groups = result.data if result.data else []
            log.info(
                "groups_listed_successfully",
                group_count=len(groups),
            )
            for group in groups:
                log.info(
                    "group_info",
                    email=group.get("email"),
                    name=group.get("name"),
                )
            return

        # Handle different error statuses
        log.error(
            "failed_to_list_groups",
            status=result.status,
            message=result.message,
            error_code=result.error_code,
        )

    except Exception as e:
        log.error("test_exception", error=str(e), exc_info=True)


def test_groups_with_members() -> None:
    """Test listing groups with their members from Google Workspace Directory API."""
    log = logger.bind(test="groups_with_members")
    log.info("starting_groups_with_members_test")

    try:
        # Get Google Workspace clients from service provider
        google_clients = get_google_workspace_clients()

        log.info("initialized_google_clients")

        request = ListGroupsWithMembersRequest(
            groups_kwargs={"query": "email:aws-*"},
            groups_filters=[lambda g: "staging" in g.get("email", "")],
        )
        # List groups with members
        result = google_clients.directory.list_groups_with_members(request)

        # Handle the result
        if result.is_success:
            groups = result.data if result.data else []
            log.info(
                "groups_with_members_listed_successfully",
                group_count=len(groups),
            )
            for group in groups:
                log.info(
                    "group_info",
                    email=group.get("email"),
                    name=group.get("name"),
                    member_count=len(group.get("members", [])),
                )
            return

        # Handle different error statuses
        log.error(
            "failed_to_list_groups_with_members",
            status=result.status,
            message=result.message,
            error_code=result.error_code,
        )

    except Exception as e:
        log.error("test_exception", error=str(e), exc_info=True)


def google_service_command(ack, client, body, respond):
    """Handle Google service command."""
    ack()
    respond("Processing Google service request...")
    # test_list_groups()
    test_groups_with_members()
    respond("Google service request completed.")
