"""Module for getting users from integrations."""

from integrations.google_workspace import google_directory
from integrations.aws import identity_store
from utils import filters
from core.logging import get_module_logger

logger = get_module_logger()


def get_users_from_integration(integration_source, **kwargs):
    processing_filters = kwargs.get("processing_filters", [])
    users = []

    match integration_source:
        case "google_directory":
            logger.info(
                "get_users_from_integration_started",
                integration_source=integration_source,
                service="Google Workspace",
            )
            users = google_directory.list_users()
        case "aws_identity_center":
            logger.info(
                "get_users_from_integration_started",
                integration_source=integration_source,
                service="AWS Identity Center",
            )
            users = identity_store.list_users()
        case _:
            return users

    for filter in processing_filters:
        users = filters.filter_by_condition(users, filter)

    logger.info(
        "get_users_from_integration_completed",
        integration_source=integration_source,
        users_count=len(users),
    )

    return users
