"""Event system - event-driven architecture.

This module re-exports infrastructure event system for backward compatibility
and provides groups-specific event types.
"""

from infrastructure.events import (
    Event,
    dispatch_background,
    dispatch_event,
    register_event_handler,
)
from modules.groups.events.events import (
    GroupMemberAddedEvent,
    GroupMemberEvent,
    GroupMemberRemovedEvent,
)

__all__ = [
    "Event",
    "register_event_handler",
    "dispatch_event",
    "dispatch_background",
    "GroupMemberEvent",
    "GroupMemberAddedEvent",
    "GroupMemberRemovedEvent",
]
