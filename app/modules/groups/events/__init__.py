"""Event system - event-driven architecture."""

from modules.groups.events.event_system import (
    register_event_handler,
    dispatch_event,
)

__all__ = [
    "register_event_handler",
    "dispatch_event",
]
