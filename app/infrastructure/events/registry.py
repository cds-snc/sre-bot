"""Event handler registry abstraction and singleton provider."""

from functools import lru_cache
from typing import Callable


class EventHandlerRegistry:
    """Registry for event handlers keyed by event type."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}

    def register(self, event_type: str, handler: Callable) -> None:
        """Register a handler for an event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    def get_handlers(self, event_type: str) -> list[Callable]:
        """Get handlers for a type plus wildcard handlers."""
        handlers = self._handlers.get(event_type, [])
        wildcard = self._handlers.get("*", [])
        return [*handlers, *wildcard]

    def get_handlers_for_event(self, event_type: str) -> list[Callable]:
        """Get handlers registered directly for an event type."""
        return list(self._handlers.get(event_type, []))

    def get_registered_events(self) -> list[str]:
        """Get all event types currently registered."""
        return list(self._handlers.keys())

    def get_handlers_by_event_type(self) -> dict[str, list[Callable]]:
        """Get a shallow copy of all handlers by event type."""
        return {
            event_type: list(handlers)
            for event_type, handlers in self._handlers.items()
        }

    def clear(self) -> None:
        """Clear all handlers from the registry."""
        self._handlers.clear()


@lru_cache(maxsize=1)
def get_event_registry() -> EventHandlerRegistry:
    """Get application-scoped event registry singleton."""
    return EventHandlerRegistry()
