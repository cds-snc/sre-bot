"""Module for getting users from integrations."""

from structlog import get_logger

from infrastructure.directory import get_directory_provider
from integrations.aws import identity_store
from utils import filters

logger = get_logger()


class DirectoryUsersUnavailableError(Exception):
    """Raised when the directory cannot supply the user list."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


def get_users_from_integration(integration_source, **kwargs):
    """Return the users of an integration source.

    The `google_directory` source yields canonical `DirectoryUser` values for
    the full directory (no limit); `aws_identity_center` still yields raw
    identity_store dicts.

    Raises:
        DirectoryUsersUnavailableError: when the directory listing fails.
    """
    log = logger.bind(
        integration=integration_source,
        operation="get_users_from_integration",
    )
    processing_filters = kwargs.get("processing_filters", [])
    users = []

    match integration_source:
        case "google_directory":
            log.info(
                "get_users_from_integration_started",
                service="Google Workspace",
            )
            result = get_directory_provider().list_users()
            if not result.is_success:
                log.error(
                    "list_users_failed",
                    error_code=result.error_code,
                    error=result.message,
                )
                raise DirectoryUsersUnavailableError(result.message, result.error_code)
            users = result.data or []
        case "aws_identity_center":
            log.info(
                "get_users_from_integration_started",
                service="AWS Identity Center",
            )
            users = identity_store.list_users()
        case _:
            return users

    for filter in processing_filters:
        users = filters.filter_by_condition(users, filter)

    logger.info(
        "get_users_from_integration_completed",
        users_count=len(users),
    )

    return users
