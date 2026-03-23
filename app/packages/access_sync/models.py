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
from typing import List, Literal, Optional


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
