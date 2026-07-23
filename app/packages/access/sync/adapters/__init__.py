"""Access Sync adapter contract.

Adapters own the full reconciliation lifecycle for a platform:
  assess current state → plan delta → execute via platform API calls.

All methods are idempotent and return OperationResult.
Adapters must never raise exceptions across this boundary.
"""

from typing import TYPE_CHECKING, Protocol

from infrastructure.operations import OperationResult

if TYPE_CHECKING:
    from packages.access.sync.domain import DesiredPlatformState, DesiredUserState
    from packages.access.sync.policies import AdapterCapabilities, PlanningContext


class AccessSyncAdapter(Protocol):
    """Contract for all platform sync adapters."""

    def capabilities(self) -> AdapterCapabilities:
        """Return the execution capabilities declared by this adapter."""
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
        """Apply an entitlement to a user (idempotent; no-op if already held)."""
        ...

    def remove_entitlement(
        self,
        user_email: str,
        entitlement_type: str,
        entitlement_id: str,
    ) -> OperationResult:
        """Remove an entitlement from a user (idempotent; no-op if already absent)."""
        ...

    def reconcile_user(
        self,
        user_email: str,
        desired_state: DesiredUserState,
        context: PlanningContext,
        dry_run: bool = False,
    ) -> OperationResult:
        """Assess current platform state, plan delta, execute changes for one user.

        The adapter owns the full reconciliation lifecycle:
          1. Read current platform state.
          2. Plan delta via PolicyEngine (internal).
          3. Execute planned actions via platform API calls.
          4. Return OperationResult[SyncOutcome].

        In dry_run mode: return plan without executing.
        """
        ...

    def reconcile_platform(
        self,
        desired_state: DesiredPlatformState,
        context: PlanningContext,
        dry_run: bool = False,
    ) -> OperationResult:
        """Batch reconcile a full platform using entitlement-shaped desired state.

        The adapter owns platform-state assessment, delta planning, and execution.
        Returns OperationResult[ReconciliationOutcome].
        """
        ...
