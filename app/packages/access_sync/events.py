"""Access Sync domain event name constants.

Event dispatch must use EventDispatcher from infrastructure.events.
This module contains only string constants — no logic, no imports.
"""

SYNC_COMPLETED = "access_sync.sync_completed"
SYNC_FAILED = "access_sync.sync_failed"

PLATFORM_SYNC_STARTED = "access_sync.platform_sync_started"
PLATFORM_SYNC_COMPLETED = "access_sync.platform_sync_completed"

MANUAL_ACTION_REQUIRED = "access_sync.manual_action_required"
