"""Access Sync adapter contract and capability models.

Adapters execute normalized actions against a specific platform's external API.
They must never implement policy logic — that belongs in policies.py.

All adapter methods are idempotent: calling them with the same inputs more than
once must produce the same result.  When an action cannot be automated, adapters
return a non-success OperationResult with a machine-readable error_code so the
service can mark the run as manual_action_required.

v1 supported entitlement_type: "group"
  entitlement_id = platform-native group identifier (e.g. AWS IC GroupId)

Future: "permission_set" for temporary elevated account assignments.
"""

from typing import Protocol, Set, TYPE_CHECKING, runtime_checkable

from infrastructure.operations import OperationResult

if TYPE_CHECKING:
    from packages.access_sync.policies import AdapterCapabilities


class AccessSyncAdapter(Protocol):
    """Contract for all platform sync adapters.

    All methods are idempotent and return OperationResult.  Adapters must not
    raise exceptions across this boundary.
    """

    def capabilities(self) -> "AdapterCapabilities":
        """Return the execution capabilities of this adapter.

        Used by PolicyEngine.plan_actions to select compatible actions.
        """
        ...

    def get_user(self, user_email: str) -> OperationResult:
        """Look up a user.

        Returns:
            SUCCESS with data if found, NOT_FOUND if the user does not exist.
        """
        ...

    def ensure_user(self, user_email: str) -> OperationResult:
        """Ensure a user account exists; create it if missing (idempotent)."""
        ...

    def disable_user(self, user_email: str) -> OperationResult:
        """Deactivate a user account (idempotent; no-op if already disabled)."""
        ...

    def remove_user(self, user_email: str) -> OperationResult:
        """Remove a user from the platform entirely (idempotent; no-op if absent)."""
        ...

    def apply_entitlement(
        self,
        user_email: str,
        entitlement_type: str,
        entitlement_id: str,
    ) -> OperationResult:
        """Apply an entitlement to a user (idempotent; no-op if already held).

        v1: entitlement_type="group", entitlement_id=<platform group id>
        """
        ...

    def remove_entitlement(
        self,
        user_email: str,
        entitlement_type: str,
        entitlement_id: str,
    ) -> OperationResult:
        """Remove an entitlement from a user (idempotent; no-op if already absent).

        v1: entitlement_type="group", entitlement_id=<platform group id>
        """
        ...

    def fetch_current_state(self, user_email: str) -> OperationResult:
        """Fetch all current entitlements and account status for a user."""
        ...

    def get_current_entitlement_ids(self, user_email: str) -> OperationResult:
        """Return the normalized set of entitlement IDs the user currently holds.

        Entitlement IDs must use the same format as ``EntitlementRule.entitlement_id``
        so the PolicyEngine can compute the delta against the desired set.

        Returns:
            ``OperationResult[Set[str]]`` with the entitlement ID set, or error.
            Returns an empty set (success) when the user exists but holds nothing.
            Returns NOT_FOUND when the user does not exist on the platform.
        """
        ...

    def list_all_provisioned_users(self) -> OperationResult:
        """Return a set of all user emails currently provisioned on this platform.

        Used by reconciliation for orphan detection: users on the platform
        whose IDP authn-group membership has since been revoked.

        Returns:
            ``OperationResult[Set[str]]`` of lowercase user emails, or error.
            Adapters that cannot enumerate their user base return NOT_IMPLEMENTED.
        """
        ...

    def list_group_members(self, group_id: str) -> OperationResult:
        """Return the set of user emails that are members of the given platform group.

        Used by reconciliation batch read phase to get platform-side group
        membership without per-user API calls.

        Args:
            group_id: Platform-native group identifier (e.g. AWS IC GroupId).

        Returns:
            ``OperationResult[Set[str]]`` of lowercase member emails, or error.
        """
        ...


@runtime_checkable
class BulkGroupMembershipAdapter(Protocol):
    """Optional high-throughput membership read capability.

    Adapters implement this protocol when they can fetch members for many
    groups in one optimized call path, reducing reconciliation read costs.
    """

    def list_members_for_groups(self, group_ids: Set[str]) -> OperationResult:
        """Return mapping of group_id -> set of lowercase member emails."""
        ...
