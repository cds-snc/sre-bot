"""Google Workspace clients for infrastructure layer.

Public API (Package Level):
- GoogleWorkspaceClients: Facade for all Google Workspace service clients
- Individual clients: DirectoryClient, DriveClient, DocsClient, SheetsClient, GmailClient
- Request models: ListGroupsWithMembersRequest (for DirectoryClient operations)
"""

from infrastructure.clients.google_workspace.directory import (
    ListGroupsWithMembersRequest,
)
from infrastructure.clients.google_workspace.facade import (
    GoogleWorkspaceClients,
    get_google_workspace_clients,
)

__all__ = [
    "GoogleWorkspaceClients",
    "ListGroupsWithMembersRequest",
    "get_google_workspace_clients",
]
