"""Groups membership event consumers.

This module contains only passive, post-write consumers (notifications)
that subscribe to canonical events emitted by the service boundary.
All write operations (adds/removes) are performed by the `service` layer.

Audit logging is now handled automatically by the centralized audit handler
(infrastructure.events.handlers.audit) which processes all events.
"""

from infrastructure.events import register_event_handler, Event
from core.logging import get_module_logger
from modules.groups.infrastructure import notifications

logger = get_module_logger()


@register_event_handler("group.member.added")
def handle_member_added(payload: Event) -> None:
    """Handle post-addition tasks (notifications only).

    Audit logging is handled automatically by the infrastructure event system.

    Expects the canonical nested event payload produced by the service, e.g.
    {"orchestration": {...}, "request": {...}}
    """
    # Send notifications
    notifications.send_group_notifications(payload)


@register_event_handler("group.member.removed")
def handle_member_removed(payload: Event) -> None:
    """Handle post-removal tasks (notifications only).

    Audit logging is handled automatically by the infrastructure event system.
    """
    # Send notifications
    notifications.send_group_notifications(payload)


@register_event_handler("group.listed")
def handle_group_listed(payload: Event) -> None:
    """Handle post-listing tasks (notifications only).

    Audit logging is handled automatically by the infrastructure event system.
    """
    # Send notifications
    notifications.send_group_notifications(payload)
