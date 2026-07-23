"""Access Sync internal domain models.

``SyncOutcome`` is the business-level result of a sync operation, carried
inside ``OperationResult.data`` for success cases.  Technical failures
(policy not found, adapter API error) surface as ``OperationResult.error``
and never produce a ``SyncOutcome``.

``SyncRunRecord`` is the persistent audit record written to DynamoDB via
``SyncRunRepository`` in store.py.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from packages.access.sync.policies import EntitlementRule


@dataclass(frozen=True)
class AdapterAssessment:
    """Current platform state assessed by the adapter for one user.

    Returned by ``AccessSyncAdapter.assess()`` so the coordinator can plan and
    execute without any heuristic inference of user existence or entitlements.

    The adapter is the sole source of truth for platform state.  When pre-fetched
    data is embedded in ``DesiredUserState`` (batch sync path), the adapter
    assess implementation uses it directly with zero additional API calls.

    Attributes:
        platform_user_exists: True when the user is provisioned on the platform.
        current_entitlement_ids: Entitlement IDs the user currently holds.
            Empty set when the user exists with no entitlements.
            Also empty when the user does not exist (see platform_user_exists).
    """

    platform_user_exists: bool
    current_entitlement_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class DesiredUserState:
    """Resolved desired state for one user on one platform.

    Built from IDP directory membership data.  The adapter is the sole
    authority for current platform state — this model carries no platform
    state fields.
    """

    user_should_exist: bool
    required_entitlements: list[EntitlementRule] = field(default_factory=list)


@dataclass(frozen=True)
class DesiredPlatformState:
    """Resolved desired state for a full platform reconciliation run."""

    desired_users: set[str] = field(default_factory=set)
    desired_members_by_entitlement: dict[str, set[str]] = field(default_factory=dict)
    entitlement_slug_by_id: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CurrentPlatformState:
    """Current platform state for a full platform reconciliation run."""

    current_users: set[str] = field(default_factory=set)
    current_members_by_entitlement: dict[str, set[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class SyncOutcome:
    """Business outcome of a completed or dry-run sync_user call.

    Attributes:
        planned_actions: Ordered list of adapter action names selected by the
            planner for this run.
        applied_actions: Ordered list of adapter action names actually executed.
            Empty for dry-run responses.
        requires_manual_action: True when one or more policy-mandated actions
            could not be automated (e.g. AWS IC disable unsupported).  The
            sync still succeeded for the actions that were automatable.
    """

    planned_actions: list[str] = field(default_factory=list)
    applied_actions: list[str] = field(default_factory=list)
    requires_manual_action: bool = False


@dataclass
class SyncRunRecord:
    """Persistent audit record of a single sync operation."""

    run_id: str
    user_email: str
    platform: str
    actions_applied: list[str]
    status: Literal["success", "partial", "failed", "manual_action_required"]
    dry_run: bool = False
    request_id: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ReconciliationOutcome:
    """Outcome of a full platform reconciliation run.

    Attributes:
        platform: Platform key that was reconciled.
        users_synced: Total number of users whose state was evaluated.
        users_converged: Users where sync_user applied at least one action.
        orphans_found: Users present on the platform but not in the IDP.
        requires_manual_action_count: Users whose sync flagged manual action.
        dry_run: True if no changes were actually executed.
        per_user: Optional mapping of email → SyncOutcome for detailed audit.
    """

    platform: str
    users_synced: int
    users_converged: int
    orphans_found: int
    requires_manual_action_count: int
    dry_run: bool = False
    per_user: dict[str, SyncOutcome] = field(default_factory=dict)
    changed_user_count: int = 0
    unchanged_user_count: int = 0
    action_counts: dict[str, int] = field(default_factory=dict)
    lifecycle_actions: dict[str, list[str]] = field(default_factory=dict)
    entitlements_by_action: dict[str, dict[str, list[str]]] = field(default_factory=dict)
