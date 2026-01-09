"""Google Workspace clients for infrastructure layer.

Public API:
- GoogleWorkspaceClients: Facade for all Google Workspace service clients
- Individual clients: DirectoryClient, DriveClient, DocsClient, SheetsClient, GmailClient

Usage:
    from infrastructure import GoogleWorkspaceClientsDep

    @router.get("/users/{user_id}")
    def get_user(user_id: str, google: GoogleWorkspaceClientsDep):
        result = google.directory.get_user(user_id)
        if result.is_success:
            return result.data
"""

from infrastructure.clients.google_workspace.facade import GoogleWorkspaceClients

__all__ = [
    "GoogleWorkspaceClients",
]
