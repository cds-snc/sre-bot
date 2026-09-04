"""DirectoryProvider protocol — IDP-agnostic contract for directory operations."""

from typing import Protocol, runtime_checkable

from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryGroupsWithMembers,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
)
from infrastructure.operations import OperationResult


@runtime_checkable
class DirectoryProvider(Protocol):
    """IDP-agnostic directory operations used by feature packages.

    All method arguments that represent canonical group emails or user emails
    are normalised to lowercase by implementors before calling the underlying
    IDP, and so are the emails carried on returned DirectoryUser,
    DirectoryMember and DirectoryGroup values — the IDP's original casing is
    not preserved. Consumers comparing returned emails against addresses
    sourced elsewhere (Slack profiles, command arguments, records stored in
    another system) must compare case-insensitively. All return values are
    wrapped in OperationResult — no exceptions cross the boundary.
    """

    def warmup(self) -> OperationResult[None]:
        """Validate connectivity/credentials and prepare hot-path resources.

        Returns:
            OperationResult: success when provider is healthy, error otherwise.
        """
        ...

    def health_check(self) -> OperationResult[None]:
        """Fast liveness check suitable for readiness/liveness probes.

        Must not make expensive remote API calls.

        Returns:
            OperationResult: success when provider considers itself live.
        """
        ...

    def get_user(self, email: str) -> OperationResult[DirectoryUser]:
        """Return a canonical user by email.

        Args:
            email: Canonical user email, normalised to lowercase.

        Returns:
            OperationResult: success with the canonical DirectoryUser.
        """
        ...

    def list_users(self, query: str = "", limit: int | None = None) -> OperationResult[list[DirectoryUser]]:
        """Return canonical users for a directory query.

        Args:
            query: Provider-agnostic query expression. Implementors translate
                this into backend-specific filter/search parameters when
                supported. Empty string requests an unfiltered list where
                supported.
            limit: Maximum number of canonical users to return. None or not
                provided requests all users (unbounded pagination).
                Implementors should stop paginating as soon as limit is reached.

        Returns:
            OperationResult: success with the canonical DirectoryUser list.
        """
        ...

    def get_group_members(
        self,
        group_key: str,
        include_member_types: set[str] | None = None,
    ) -> OperationResult[list[DirectoryMember]]:
        """Return all members of a group.

        Args:
            group_key: Fully-qualified group email (normalised to lowercase).
            include_member_types: Optional set of member types to include
                (for example ``{"USER"}``, ``{"GROUP"}``, or both). If not
                provided, providers should return all member types.

        Returns:
            OperationResult: success with the DirectoryMember list for the group.
        """
        ...

    def get_group(self, group_key: str) -> OperationResult[DirectoryGroup]:
        """Return a canonical group by key.

        Args:
            group_key: Fully-qualified group email (normalised to lowercase).

        Returns:
            OperationResult: success with the canonical DirectoryGroup.
        """
        ...

    def add_group_member(
        self,
        group_key: str,
        user_email: str,
        role: str = "MEMBER",
    ) -> OperationResult[DirectoryMember]:
        """Add a user membership to a group.

        Args:
            group_key: Fully-qualified group email (normalised to lowercase).
            user_email: User email to add (normalised to lowercase).
            role: Provider-agnostic membership role hint (default: MEMBER).

        Returns:
            OperationResult: success with the added DirectoryMember.
        """
        ...

    def remove_group_member(
        self,
        group_key: str,
        user_email: str,
    ) -> OperationResult[None]:
        """Remove a user membership from a group.

        Args:
            group_key: Fully-qualified group email (normalised to lowercase).
            user_email: User email to remove (normalised to lowercase).

        Returns:
            OperationResult: success with no payload when removal completes.
        """
        ...

    def check_membership(self, group_key: str, user_email: str) -> OperationResult[MembershipCheckResult]:
        """Check whether a user is a member of a group.

        Args:
            group_key: Fully-qualified group email (normalised to lowercase).
            user_email: User email to check (compared case-insensitively).

        Returns:
            OperationResult: success with the MembershipCheckResult.
        """
        ...

    def list_groups(self, query: str = "", limit: int | None = None) -> OperationResult[list[DirectoryGroup]]:
        """List groups matching a query expression.

        Args:
            query: Provider-agnostic query expression translated by each
                implementor into backend-specific list parameters. Empty
                string requests an unfiltered list of all groups.
            limit: Maximum number of canonical groups to return. None or not
                provided requests all groups (unbounded pagination).

        Returns:
            OperationResult: success with the matching DirectoryGroup list.
        """
        ...

    def list_groups_with_members(
        self,
        query: str = "",
        limit: int | None = None,
        include_member_types: set[str] | None = None,
    ) -> OperationResult[DirectoryGroupsWithMembers]:
        """List groups together with their members in one composition.

        Implementors should use a provider-native batch API so the cost stays
        proportional to the number of member pages rather than the number of
        groups.  Groups whose members could not be fetched are returned in
        ``failures`` rather than failing the whole result, because the
        OperationStatus set is closed (decisions/operation-result.md).  Groups
        with zero members are included.

        Args:
            query: Provider-agnostic query expression, as for ``list_groups``.
            limit: Maximum number of groups to return, or None for all groups.
            include_member_types: Optional set of member types to include
                (for example ``{"USER"}``). If not provided, return all types.

        Returns:
            OperationResult: success with the DirectoryGroupsWithMembers payload.
        """
        ...

    def get_user_groups(self, user_email: str) -> OperationResult[list[DirectoryGroup]]:
        """Return all groups the user is a direct member of.

        Uses an inverse group lookup (e.g. ``groups.list?userKey=``) so a
        single call replaces the per-group ``check_membership`` loop in the
        single-user sync path.

        Note: Returns direct memberships only — transitive membership through
        nested sub-groups is not expanded.

        Args:
            user_email: Canonical user email, normalised to lowercase.

        Returns:
            OperationResult: success with the list of DirectoryGroup the user
            belongs to.
        """
        ...

    def get_group_members_batch(
        self,
        group_keys: list[str],
        include_member_types: set[str] | None = None,
    ) -> OperationResult[dict[str, list[DirectoryMember]]]:
        """Return the member list for multiple groups in a single batch call.

        Implementors should use a provider-native batch API when available so
        the cost is one network round-trip regardless of how many groups are
        queried.  Falls back gracefully for providers that do not support
        batching.

        Args:
            group_keys: Fully-qualified group emails (normalised to lowercase).
            include_member_types: Optional set of member types to include
                (for example ``{"USER"}``). If not provided, return all types.

        Returns:
            OperationResult: success with a dict mapping each group_key to its
            DirectoryMember list.  Groups with no members map to an empty list.
        """
        ...
