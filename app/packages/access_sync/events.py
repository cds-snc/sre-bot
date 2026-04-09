"""Access Sync domain event name constants.

Use these constants when dispatching or subscribing to Access Sync events
via ``EventDispatcher`` from ``infrastructure.events``.  String literals
must not be used directly in coordinator or transport code.

This module contains string constants only — no imports, no logic.
"""

SYNC_COMPLETED = "access_sync.sync_completed"
SYNC_FAILED = "access_sync.sync_failed"

PLATFORM_SYNC_STARTED = "access_sync.platform_sync_started"
PLATFORM_SYNC_COMPLETED = "access_sync.platform_sync_completed"

MANUAL_ACTION_REQUIRED = "access_sync.manual_action_required"
