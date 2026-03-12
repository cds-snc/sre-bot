"""Google Workspace implementation of DirectoryProvider."""

import structlog

from infrastructure.clients.google_workspace import GoogleWorkspaceClients
from infrastructure.operations import OperationResult

logger = structlog.get_logger()


class GoogleDirectoryProvider:
    """DirectoryProvider backed by Google Workspace Directory API.

    Receives a GoogleWorkspaceClients facade injected by the factory.  Direct
    instantiation of Google API credentials or service clients inside this
    class is forbidden — use build_google_directory_provider() from the factory
    module instead.
    """

    def __init__(self, google_clients: GoogleWorkspaceClients) -> None:
        """Initialise with injected Google Workspace clients facade.

        Args:
            google_clients: Configured GoogleWorkspaceClients facade.
        """
        self._directory = google_clients.directory

    def warmup(self) -> OperationResult:
        """Validate connectivity by issuing a minimal list-groups call.

        Returns:
            OperationResult: success when the API responds successfully.
        """
        log = logger.bind(provider="google", operation="warmup")
        log.info("directory_warmup_started")
        result = self._directory.list_groups(maxResults=1)
        if result.is_success:
            log.info("directory_warmup_completed")
        else:
            log.error("directory_warmup_failed", error=result.message)
        return result

    def health_check(self) -> OperationResult:
        """Return a fast liveness result without making remote calls.

        Returns:
            OperationResult: always success.
        """
        return OperationResult.success()

    def get_group_members(self, group_key: str) -> OperationResult:
        """Return the member list for a group.

        Args:
            group_key: Group email or unique ID — normalised to lowercase.

        Returns:
            OperationResult: success with data as list of member dicts.
        """
        return self._directory.list_members(group_key.lower())

    def check_membership(self, group_key: str, email: str) -> OperationResult:
        """Check whether a user is a member of a group.

        Fetches all members and performs a case-insensitive email comparison
        locally to avoid a separate get-member API call.

        Args:
            group_key: Group email or unique ID — normalised to lowercase.
            email: User email to check.

        Returns:
            OperationResult: success with data={"is_member": bool}.
                Returns the error result unchanged when list_members fails.
        """
        result = self._directory.list_members(group_key.lower())
        if not result.is_success:
            return result
        members = result.data or []
        is_member = any(m.get("email", "").lower() == email.lower() for m in members)
        return OperationResult.success(data={"is_member": is_member})

    def list_groups(self, query: str) -> OperationResult:
        """List groups matching a query string.

        Args:
            query: IDP-specific query string passed to the Directory API.

        Returns:
            OperationResult: success with data as list of group dicts.
        """
        return self._directory.list_groups(query=query)
