"""Unit tests for event handler registry."""

import pytest

from infrastructure.events.registry import EventHandlerRegistry

pytestmark = pytest.mark.unit


def test_registry_register_and_retrieve() -> None:
    """A registered handler is returned for its event type."""
    registry = EventHandlerRegistry()

    def handler(event):
        return event

    registry.register("test.event", handler)

    handlers = registry.get_handlers_for_event("test.event")
    assert handlers == [handler]


def test_registry_wildcard_handlers() -> None:
    """Wildcard handlers are returned for any event type."""
    registry = EventHandlerRegistry()

    def wildcard_handler(event):
        return event

    registry.register("*", wildcard_handler)

    handlers = registry.get_handlers("any.event")
    assert handlers == [wildcard_handler]


def test_registry_clear() -> None:
    """Clear removes all handlers."""
    registry = EventHandlerRegistry()

    def handler(event):
        return event

    registry.register("test.event", handler)
    registry.clear()

    assert registry.get_handlers_for_event("test.event") == []
    assert registry.get_registered_events() == []


def test_registry_multiple_handlers_same_type() -> None:
    """Multiple handlers can be registered for a single event type."""
    registry = EventHandlerRegistry()

    def handler_one(event):
        return event

    def handler_two(event):
        return event

    registry.register("test.event", handler_one)
    registry.register("test.event", handler_two)

    handlers = registry.get_handlers_for_event("test.event")
    assert handlers == [handler_one, handler_two]


def test_registry_isolation() -> None:
    """Separate registries do not share state."""
    first = EventHandlerRegistry()
    second = EventHandlerRegistry()

    def handler(event):
        return event

    first.register("test.event", handler)

    assert first.get_handlers_for_event("test.event") == [handler]
    assert second.get_handlers_for_event("test.event") == []
