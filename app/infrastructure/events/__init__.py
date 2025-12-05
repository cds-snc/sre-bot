"""Infrastructure event system - centralized event dispatcher.

The event system provides a lightweight, in-process event dispatcher
for audit trails, notifications, and cross-module communication.

Usage:

    from infrastructure.events import Event, register_event_handler, dispatch_event

    # Define a handler
    @register_event_handler("group.member.added")
    def handle_member_added(event: Event) -> None:
        # Process the event
        pass

    # Dispatch an event
    event = Event(
        event_type="group.member.added",
        user_email="user@example.com",
        metadata={"group_id": "123", "member": "newmember@example.com"}
    )
    dispatch_event(event)

    # Or dispatch in background
    from infrastructure.events import dispatch_background
    dispatch_background(event)
"""

from infrastructure.events.dispatcher import (
    dispatch_background,
    dispatch_event,
    get_handlers_for_event,
    get_registered_events,
    register_event_handler,
    shutdown_event_executor,
    start_event_executor,
)
from infrastructure.events.discovery import (
    discover_and_register_handlers,
    get_registered_handlers_by_event_type,
    log_registered_handlers,
)
from infrastructure.events.models import Event

__all__ = [
    "Event",
    "dispatch_event",
    "dispatch_background",
    "register_event_handler",
    "get_registered_events",
    "get_handlers_for_event",
    "start_event_executor",
    "shutdown_event_executor",
    "discover_and_register_handlers",
    "get_registered_handlers_by_event_type",
    "log_registered_handlers",
]
