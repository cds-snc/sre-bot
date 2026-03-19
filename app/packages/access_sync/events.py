"""Access Sync domain event name constants.

Event dispatch must use EventDispatcher from infrastructure.events.
This module contains only string constants — no logic, no imports.
"""

SYNC_STARTED = "access_sync.sync_started"
SYNC_COMPLETED = "access_sync.sync_completed"
SYNC_FAILED = "access_sync.sync_failed"

RECONCILIATION_STARTED = "access_sync.reconciliation_started"
RECONCILIATION_COMPLETED = "access_sync.reconciliation_completed"
RECONCILIATION_FAILED = "access_sync.reconciliation_failed"

USER_PROVISIONED = "access_sync.user_provisioned"
USER_DEPROVISIONED = "access_sync.user_deprovisioned"

ENTITLEMENT_APPLIED = "access_sync.entitlement_applied"
ENTITLEMENT_REMOVED = "access_sync.entitlement_removed"

MANUAL_ACTION_REQUIRED = "access_sync.manual_action_required"
