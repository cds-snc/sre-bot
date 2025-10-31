"""Groups membership event consumers.

This module contains only passive, post-write consumers (audit and
notifications) that subscribe to canonical events emitted by the service
boundary. All write operations (adds/removes) are performed by the
`service` layer; legacy handlers that invoked `base` helpers have been
removed to enforce the new architecture.
"""

from typing import Dict, Any

from modules.groups.event_system import register_event_handler
from core.logging import get_module_logger
from modules.groups.audit import log_group_action
from modules.groups.notifications import send_group_notifications

logger = get_module_logger()


@register_event_handler("group.member.added")
def handle_member_added(payload: Dict[str, Any]) -> None:
    """Handle post-addition tasks (audit + notifications).

    Expects the canonical nested event payload produced by the service, e.g.
    {"orchestration": {...}, "request": {...}, "event_type": "group.member.added"}
    """

    # Log to Sentinel for audit
    log_group_action(payload)

    # Send notifications
    send_group_notifications(payload)


@register_event_handler("group.member.removed")
def handle_member_removed(payload: Dict[str, Any]) -> None:
    """Handle post-removal tasks (audit + notifications)."""

    # Log to Sentinel for audit
    log_group_action(payload)

    # Send notifications
    send_group_notifications(payload)
