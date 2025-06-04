"""Google Meet API integration module."""

from googleapiclient.discovery import Resource  # type: ignore
from integrations.google_next.service import (
    execute_google_api_call,
    handle_google_api_errors,
    get_google_service,
)
from core.logging import get_module_logger

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/meet.space.created",
]

logger = get_module_logger()


class GoogleMeet:
    """
    A class to simplify the use of various Google Meet API operations across modules.

    This class provides methods to interact with the Google Workspace Meet API, including creating new meetings, updating existing meetings, and retrieving meeting details, and includes error handling for Google API errors.

    While this class aims to simplify the usage of the Google Meet API, it is always possible
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
        self.scopes = scopes if scopes else DEFAULT_SCOPES
        self.delegated_email = delegated_email
        self.service = service if service else self._get_google_service()
        logger.debug(
            "google_meet_initialized",
            service_type="meet",
            scopes=scopes,
            delegated_email=delegated_email,
        )

    def _get_google_service(self) -> Resource:
        """Get authenticated directory service for Google Workspace."""
        logger.debug(
            "getting_meet_service",
            service_type="meet",
            scopes=self.scopes,
            delegated_email=self.delegated_email,
        )
        return get_google_service("meet", "v2", self.scopes, self.delegated_email)

    @handle_google_api_errors
    def create_space(self):
        """Creates a new and empty space in Google Meet."""
        logger.info(
            "creating_meet_space",
            service="google_meet",
        )
        config = {"accessType": "TRUSTED", "entryPointAccess": "ALL"}
        return execute_google_api_call(
            self.service, "spaces", "create", body={"config": config}
        )
