"""Event dispatcher for infrastructure event system.

Provides centralized event dispatcher with in-process handler registry.
Handlers are registered with decorators and called synchronously when
events are dispatched.
"""

import atexit
from functools import lru_cache
from typing import Any, Callable

import structlog
from infrastructure.events.models import Event
from infrastructure.events.registry import get_event_registry
from infrastructure.events.service import EventDispatcher

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def get_default_event_dispatcher() -> EventDispatcher:
    """Get module-level default dispatcher used by wrapper functions."""
    return EventDispatcher(registry=get_event_registry())


def register_event_handler(event_type: str):
    """Decorator to register an event handler for a specific event type.

    Args:
        event_type: The type of event to handle (e.g., 'group.member.added').

    Returns:
        Decorator function that registers the handler.
    """

    def decorator(handler_func: Callable) -> Callable:
        registry = get_event_registry()
        registry.register(event_type, handler_func)
        handler_name = getattr(handler_func, "__name__", "unknown")
        log = logger.bind(handler=handler_name, event_type=event_type)
        log.debug(
            "registered_event_handler",
            total_handlers=len(registry.get_handlers_for_event(event_type)),
        )
        return handler_func

    return decorator


def dispatch_event(event: Event) -> list[Any]:
    """Dispatch event synchronously to all registered handlers.

    All handlers for the event type are called in order, followed by
    wildcard handlers registered for "*". If a handler raises an exception,
    it is caught and logged, but processing continues with remaining handlers.

    Args:
        event: The event to dispatch.

    Returns:
        List of return values from all handlers.
    """
    return get_default_event_dispatcher().dispatch(event)


def start_event_executor(max_workers: int = 4) -> None:
    """Explicitly start the background executor (optional).

    Args:
        max_workers: Maximum number of worker threads.
    """
    get_default_event_dispatcher().start_executor(max_workers=max_workers)


def shutdown_event_executor(wait: bool = True) -> None:
    """Shut down the background executor and prevent further submissions.

    This function is idempotent and can be called safely multiple times.

    Args:
        wait: If True, wait for pending tasks to complete.
    """
    get_default_event_dispatcher().shutdown_executor(wait=wait)


@atexit.register
def _atexit_shutdown():
    """Best-effort shutdown at process exit."""
    try:
        shutdown_event_executor(wait=False)
    except Exception:
        pass


def dispatch_background(event: Event) -> None:
    """Submit background dispatch to the internal executor.

    Provides fire-and-forget semantics. Any exceptions thrown by handlers
    are caught and logged inside the worker so callers are not affected.
    If the executor has been shut down, submissions are ignored and an
    error is logged.

    Args:
        event: The event to dispatch in background.
    """
    get_default_event_dispatcher().dispatch_background(event)


def get_registered_events() -> list[str]:
    """Get list of all registered event types.

    Returns:
        List of event type strings.
    """
    return get_event_registry().get_registered_events()


def get_handlers_for_event(event_type: str) -> list[Callable]:
    """Get all handlers registered for a specific event type.

    Args:
        event_type: The event type to query.

    Returns:
        List of handler functions.
    """
    return get_event_registry().get_handlers_for_event(event_type)


def clear_handlers() -> None:
    """Clear all registered handlers.

    WARNING: This is intended for testing only.
    """
    get_event_registry().clear()
    logger.debug("cleared_all_event_handlers")
