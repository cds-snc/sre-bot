"""Access Sync domain event name constants.

Use these constants when dispatching or subscribing to Access Sync events
via ``EventDispatcher`` from ``infrastructure.events``.  String literals
must not be used directly in coordinator or transport code.

This module contains event name constants only.
"""

from packages.access.common.events import (
    SYNC_COMPLETED as COMMON_SYNC_COMPLETED,
)
from packages.access.common.events import (
    SYNC_FAILED as COMMON_SYNC_FAILED,
)

SYNC_COMPLETED = COMMON_SYNC_COMPLETED
SYNC_FAILED = COMMON_SYNC_FAILED

PLATFORM_SYNC_STARTED = "access_sync.platform_sync_started"
PLATFORM_SYNC_COMPLETED = "access_sync.platform_sync_completed"

MANUAL_ACTION_REQUIRED = "access_sync.manual_action_required"
