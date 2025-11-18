"""Event system - event-driven architecture."""

from modules.groups.events.system import (
    register_event_handler,
    dispatch_event,
)

__all__ = [
    "register_event_handler",
    "dispatch_event",
]
