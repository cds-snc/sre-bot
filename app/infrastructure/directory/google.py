"""Google Workspace implementation of DirectoryProvider."""

from typing import Any

import structlog

from infrastructure.clients.google_workspace import GoogleWorkspaceClients
from infrastructure.directory import (
    DirectoryGroup,
    DirectoryMember,
    MembershipCheckResult,
)
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

    def _build_directory_member(self, item: dict[str, Any]) -> DirectoryMember:
        """Convert a Google member record into a canonical directory member."""

        return DirectoryMember(
            email=str(item.get("email", "")).lower(),
            member_id=item.get("id"),
            role=item.get("role"),
            provider="google",
        )

    def _build_directory_group(self, item: dict[str, Any]) -> DirectoryGroup:
        """Convert a Google group record into a canonical directory group."""

        email = item.get("email")
        return DirectoryGroup(
            group_key=str(email or "").lower(),
            email=email,
            name=item.get("name"),
            description=item.get("description"),
            provider="google",
        )

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
            OperationResult: success with data={"members": list[DirectoryMember]}.
        """
        result = self._directory.list_members(group_key.lower())
        if not result.is_success:
            return result

        members = [
            self._build_directory_member(item)
            for item in (result.data or [])
            if item.get("email")
        ]
        return OperationResult.success(data={"members": members})

    def check_membership(self, group_key: str, email: str) -> OperationResult:
        """Check whether a user is a member of a group.

        Fetches all members and performs a case-insensitive email comparison
        locally to avoid a separate get-member API call.

        Args:
            group_key: Group email or unique ID — normalised to lowercase.
            email: User email to check.

        Returns:
            OperationResult: success with data={"membership": MembershipCheckResult}.
                Returns the error result unchanged when list_members fails.
        """
        normalized_group = group_key.lower()
        normalized_email = email.lower()

        result = self._directory.list_members(normalized_group)
        if not result.is_success:
            return result

        is_member = any(
            item.get("email", "").lower() == normalized_email
            for item in (result.data or [])
        )
        membership = MembershipCheckResult(
            group_key=normalized_group,
            email=normalized_email,
            is_member=is_member,
        )
        return OperationResult.success(data={"membership": membership})

    def list_groups(self, query: str) -> OperationResult:
        """List groups matching a query string.

        Args:
            query: IDP-specific query string passed to the Directory API.

        Returns:
            OperationResult: success with data={"groups": list[DirectoryGroup]}.
        """
        result = self._directory.list_groups(query=query)
        if not result.is_success:
            return result

        groups = [
            self._build_directory_group(item)
            for item in (result.data or [])
            if item.get("email")
        ]
        return OperationResult.success(data={"groups": groups})
