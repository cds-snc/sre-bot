"""Module for getting users from integrations."""
from logging import getLogger
from integrations.google_workspace import google_directory
from integrations.aws import identity_store
from utils import filters

logger = getLogger(__name__)


def get_users_from_integration(integration_source, **kwargs):
    processing_filters = kwargs.get("processing_filters", [])
    users = []

    match integration_source:
        case "google_directory":
            logger.info("Getting Google Workspace users.")
            users = google_directory.list_users()
        case "aws_identity_center":
            logger.info("Getting AWS Identity Center users.")
            users = identity_store.list_users()
        case _:
            return users
    for filter in processing_filters:
        users = filters.filter_by_condition(users, filter)

    return users
