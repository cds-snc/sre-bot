"""DirectoryProvider protocol — IDP-agnostic contract for directory operations."""

from typing import Protocol, TypedDict, runtime_checkable

from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
)
from infrastructure.operations import OperationResult


class DirectoryUserData(TypedDict):
    """Canonical payload for get_user success results."""

    user: DirectoryUser


class DirectoryUsersData(TypedDict):
    """Canonical payload for list_users success results."""

    users: list[DirectoryUser]


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

    All method arguments that represent canonical group emails or user emails
    are normalised to lowercase by implementors before calling the underlying
    IDP. All return values are wrapped in OperationResult — no exceptions cross
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

    def get_user(self, email: str) -> OperationResult:
        """Return a canonical user by email.

        Args:
            email: Canonical user email, normalised to lowercase.

        Returns:
            OperationResult: success with data matching DirectoryUserData.
        """
        ...

    def list_users(self, query: str = "", limit: int = 100) -> OperationResult:
        """Return canonical users for a directory query.

        Args:
            query: Provider-specific query string.
            limit: Maximum number of canonical users to return.

        Returns:
            OperationResult: success with data matching DirectoryUsersData.
        """
        ...

    def get_group_members(self, group_key: str) -> OperationResult:
        """Return all members of a group.

        Args:
            group_key: Canonical managed-group email (normalised to lowercase).

        Returns:
            OperationResult: success with data matching DirectoryMembersData.
        """
        ...

    def check_membership(self, group_key: str, user_email: str) -> OperationResult:
        """Check whether a user is a member of a group.

        Args:
            group_key: Canonical managed-group email (normalised to lowercase).
            user_email: User email to check (compared case-insensitively).

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
