"""Shared cross-sub-package Access event names.

These are the contract strings used at package boundaries.
"""

# Emitted by packages/access/request/, subscribed by packages/access/sync/
REQUEST_APPROVED = "access_request_approved"

# Emitted by packages/access/sync/, subscribed by packages/access/request/
SYNC_COMPLETED = "access_sync.sync_completed"
SYNC_FAILED = "access_sync.sync_failed"
