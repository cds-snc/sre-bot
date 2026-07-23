"""DirectoryProvider protocol — IDP-agnostic contract for directory operations."""

from typing import Protocol, runtime_checkable

from infrastructure.directory.models import (
    DirectoryGroup,
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
    IDP. All return values are wrapped in OperationResult — no exceptions cross
    the boundary.
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

    def list_users(self, query: str = "", limit: int = 100) -> OperationResult[list[DirectoryUser]]:
        """Return canonical users for a directory query.

        Args:
            query: Provider-agnostic query expression. Implementors translate
                this into backend-specific filter/search parameters when
                supported. Empty string requests an unfiltered list where
                supported.
            limit: Maximum number of canonical users to return. Implementors
                should enforce this at the API layer when possible and
                truncate locally when provider pagination semantics differ.

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
            group_key: Canonical managed-group email (normalised to lowercase).
            include_member_types: Optional set of member types to include
                (for example ``{"USER"}``, ``{"GROUP"}``, or both). If not
                provided, providers should return all member types.

        Returns:
            OperationResult: success with the DirectoryMember list for the group.
        """
        ...

    def get_group(self, group_key: str) -> OperationResult[DirectoryGroup]:
        """Return a canonical managed group by key.

        Args:
            group_key: Canonical managed-group email or provider-agnostic
                managed-group slug (for example, ``sg-aws-authn``).

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
        """Add a user membership to a managed group.

        Args:
            group_key: Canonical managed-group email or provider-agnostic
                managed-group slug (for example, ``sg-aws-authn``).
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
        """Remove a user membership from a managed group.

        Args:
            group_key: Canonical managed-group email or provider-agnostic
                managed-group slug (for example, ``sg-aws-authn``).
            user_email: User email to remove (normalised to lowercase).

        Returns:
            OperationResult: success with no payload when removal completes.
        """
        ...

    def check_membership(self, group_key: str, user_email: str) -> OperationResult[MembershipCheckResult]:
        """Check whether a user is a member of a group.

        Args:
            group_key: Canonical managed-group email or provider-agnostic
                managed-group slug (for example, ``sg-aws-authn``).
            user_email: User email to check (compared case-insensitively).

        Returns:
            OperationResult: success with the MembershipCheckResult.
        """
        ...

    def list_groups(self, query: str) -> OperationResult[list[DirectoryGroup]]:
        """List groups matching a query expression.

        Args:
            query: Provider-agnostic query expression translated by each
                implementor into backend-specific list parameters.

        Returns:
            OperationResult: success with the matching DirectoryGroup list.
        """
        ...

    def get_user_groups(self, user_email: str) -> OperationResult[list[DirectoryGroup]]:
        """Return all groups the user is a direct member of.

        Uses an inverse group lookup (e.g. ``groups.list?userKey=``) so a
        single call replaces the per-group ``check_membership`` loop in the
        single-user sync path.

        Note: Returns direct memberships only — transitive membership through
        nested sub-groups is not expanded.  Managed ``sg-*`` security groups
        use flat membership, making this safe for the single-user sync hot path.

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
            group_keys: Canonical managed-group emails (normalised to lowercase).
            include_member_types: Optional set of member types to include
                (for example ``{"USER"}``). If not provided, return all types.

        Returns:
            OperationResult: success with a dict mapping each group_key to its
            DirectoryMember list.  Groups with no members map to an empty list.
        """
        ...
