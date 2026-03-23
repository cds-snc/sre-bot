"""Access Sync internal domain models.

``SyncOutcome`` is the business-level result of a sync operation, carried
inside ``OperationResult.data`` for success cases.  Technical failures
(policy not found, adapter API error) surface as ``OperationResult.error``
and never produce a ``SyncOutcome``.

``SyncRunRecord`` is the persistent audit record written to DynamoDB via
``SyncRunRepository`` in store.py.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from packages.access_sync.policies import EntitlementRule


@dataclass(frozen=True)
class MembershipContext:
    """Pre-fetched IDP membership result for a single user on one platform.

    Built once per platform sync run by ``PlatformSyncService._build_desired_state``
    and passed directly to ``UserSyncService.sync_user_from_context``.
    Eliminates all per-user IDP membership calls during batch platform sync —
    directory reads are O(groups) for the whole run, not O(users × groups).

    Attributes:
        user_should_exist: True if the user is a member of the platform authn group.
        required_entitlements: Entitlement rules the user individually qualifies
            for, derived from pre-fetched membership in each entitlement group.
    """

    user_should_exist: bool
    required_entitlements: List[EntitlementRule]


@dataclass(frozen=True)
class SyncOutcome:
    """Business outcome of a completed or dry-run sync_user call.

    Attributes:
        applied_actions: Ordered list of adapter action names executed (or
            planned, for dry-run).
        requires_manual_action: True when one or more policy-mandated actions
            could not be automated (e.g. AWS IC disable unsupported).  The
            sync still succeeded for the actions that were automatable.
    """

    applied_actions: List[str]
    requires_manual_action: bool = False


@dataclass
class SyncRunRecord:
    """Persistent audit record of a single sync operation."""

    run_id: str
    user_email: str
    platform: str
    actions_applied: List[str]
    status: Literal["success", "partial", "failed", "manual_action_required"]
    dry_run: bool = False
    request_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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
    per_user: Dict[str, SyncOutcome] = field(default_factory=dict)
