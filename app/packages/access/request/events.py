"""Access Requests domain event name constants.

Use these constants when dispatching or subscribing to Access Requests events
via ``EventDispatcher`` from ``infrastructure.events``.  String literals
must not be used directly in service or transport code.

This module contains event name constants only.  No imports, no logic beyond
importing the shared cross-package constant for REQUEST_APPROVED.
"""

from packages.access.common.events import REQUEST_APPROVED as _COMMON_REQUEST_APPROVED

# Emitted by this package; consumed by packages/access/sync/
REQUEST_APPROVED = _COMMON_REQUEST_APPROVED  # "access_request_approved"

# Internal lifecycle events emitted by this package only
REQUEST_SUBMITTED = "access_requests.request_submitted"
REQUEST_REJECTED = "access_requests.request_rejected"
REQUEST_CANCELLED = "access_requests.request_cancelled"
REQUEST_EXPIRED = "access_requests.request_expired"
REQUEST_COMPLETED = "access_requests.request_completed"
REQUEST_FAILED = "access_requests.request_failed"
APPROVAL_REQUIRED = "access_requests.approval_required"
