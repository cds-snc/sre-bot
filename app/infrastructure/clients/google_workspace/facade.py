"""Google Workspace clients facade for all service operations."""

from typing import TYPE_CHECKING

import structlog

from infrastructure.clients.google_workspace.directory import DirectoryClient
from infrastructure.clients.google_workspace.session_provider import SessionProvider

if TYPE_CHECKING:
    from infrastructure.configuration.integrations.google import (
        GoogleWorkspaceSettings,
    )

logger = structlog.get_logger()


class GoogleWorkspaceClients:
    """Facade for all Google Workspace service clients.

    Composes per-service clients (Directory, Drive, Docs, Sheets, Gmail) and
    exposes them as attributes for IDE discoverability.

    Args:
        google_settings: Google Workspace configuration from settings.google_workspace

    Attributes:
        directory: DirectoryClient for users, groups, and members operations

    Usage:
        @router.get("/users/{user_id}")
        def get_user(user_id: str, google: GoogleWorkspaceClientsDep):
            result = google.directory.get_user(user_id)
            if result.is_success:
                return result.data
    """

    _session_provider: SessionProvider
    directory: DirectoryClient

    def __init__(self, google_settings: "GoogleWorkspaceSettings") -> None:
        """Initialize Google Workspace clients facade.

        Args:
            google_settings: Google Workspace configuration
        """
        self._session_provider = SessionProvider(
            credentials_json=google_settings.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE,
            default_delegated_email=google_settings.SRE_BOT_EMAIL,
            default_scopes=[],  # Each service specifies its own scopes
        )

        # Initialize service clients
        self.directory = DirectoryClient(
            session_provider=self._session_provider,
            default_customer_id=google_settings.GOOGLE_WORKSPACE_CUSTOMER_ID,
        )
        # self.sheets = SheetsClient(...)
        # self.gmail = GmailClient(...)

        self._logger = logger.bind(component="google_workspace_clients")
