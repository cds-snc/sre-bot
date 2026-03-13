"""DirectoryProvider protocol — IDP-agnostic contract for directory operations."""

from typing import Protocol, TypedDict, runtime_checkable

from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    MembershipCheckResult,
)
from infrastructure.operations import OperationResult


class DirectoryMembersData(TypedDict):
    """Canonical payload for get_group_members success results."""

    members: list[DirectoryMember]


class DirectoryGroupsData(TypedDict):
    """Canonical payload for list_groups success results."""

    groups: list[DirectoryGroup]


class DirectoryMembershipData(TypedDict):
    """Canonical payload for check_membership success results."""

    membership: MembershipCheckResult


@runtime_checkable
class DirectoryProvider(Protocol):
    """IDP-agnostic directory operations used by feature packages.

    All method arguments that represent group keys or email addresses are
    normalised to lowercase by implementors before calling the underlying IDP.
    All return values are wrapped in OperationResult — no exceptions cross
    the boundary.
    """

    def warmup(self) -> OperationResult:
        """Validate connectivity/credentials and prepare hot-path resources.

        Returns:
            OperationResult: success when provider is healthy, error otherwise.
        """
        ...

    def health_check(self) -> OperationResult:
        """Fast liveness check suitable for readiness/liveness probes.

        Must not make expensive remote API calls.

        Returns:
            OperationResult: success when provider considers itself live.
        """
        ...

    def get_group_members(self, group_key: str) -> OperationResult:
        """Return all members of a group.

        Args:
            group_key: Group email or unique ID (normalised to lowercase).

        Returns:
            OperationResult: success with data matching DirectoryMembersData.
        """
        ...

    def check_membership(self, group_key: str, email: str) -> OperationResult:
        """Check whether a user is a member of a group.

        Args:
            group_key: Group email or unique ID (normalised to lowercase).
            email: User email to check (compared case-insensitively).

        Returns:
            OperationResult: success with data matching DirectoryMembershipData.
        """
        ...

    def list_groups(self, query: str) -> OperationResult:
        """List groups matching a query or prefix.

        Args:
            query: IDP-specific query string or group email prefix.

        Returns:
            OperationResult: success with data matching DirectoryGroupsData.
        """
        ...
