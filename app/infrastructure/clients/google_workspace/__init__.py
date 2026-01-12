"""Google Workspace clients for infrastructure layer.

Public API (Package Level):
- GoogleWorkspaceClients: Facade for all Google Workspace service clients
- Individual clients: DirectoryClient, DriveClient, DocsClient, SheetsClient, GmailClient
- Request models: ListGroupsWithMembersRequest (for DirectoryClient operations)

Note: Application code should import from infrastructure.services, not directly from this package.

Developer Usage (Recommended):
    from infrastructure.services import GoogleWorkspaceClientsDep, ListGroupsWithMembersRequest

    @router.get("/groups")
    def list_groups(google: GoogleWorkspaceClientsDep):
        request = ListGroupsWithMembersRequest(
            groups_kwargs={"query": "email:aws-*"},
            exclude_empty_groups=True
        )
        result = google.directory.list_groups_with_members(request)
        if result.is_success:
            return result.data
"""

from infrastructure.clients.google_workspace.directory import (
    ListGroupsWithMembersRequest,
)
from infrastructure.clients.google_workspace.facade import GoogleWorkspaceClients

__all__ = [
    "GoogleWorkspaceClients",
    "ListGroupsWithMembersRequest",
]
