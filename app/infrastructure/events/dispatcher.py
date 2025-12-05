"""Event dispatcher for infrastructure event system.

Provides centralized event dispatcher with in-process handler registry.
Handlers are registered with decorators and called synchronously when
events are dispatched.
"""

import atexit
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

from core.logging import get_module_logger
from infrastructure.events.models import Event

logger = get_module_logger()

# Event handler registry: event_type -> list of handlers
EVENT_HANDLERS: Dict[str, List[Callable]] = {}

# Managed executor for background dispatches
_EXECUTOR: Optional[ThreadPoolExecutor] = None
_executor_lock = Lock()
_executor_shutdown = False


def register_event_handler(event_type: str):
    """Decorator to register an event handler for a specific event type.

    Args:
        event_type: The type of event to handle (e.g., 'group.member.added').

    Returns:
        Decorator function that registers the handler.
    """

    def decorator(handler_func: Callable) -> Callable:
        if event_type not in EVENT_HANDLERS:
            EVENT_HANDLERS[event_type] = []
        EVENT_HANDLERS[event_type].append(handler_func)
        handler_name = getattr(handler_func, "__name__", "unknown")
        logger.debug(
            "registered_event_handler",
            handler=handler_name,
            event_type=event_type,
            total_handlers=len(EVENT_HANDLERS[event_type]),
        )
        return handler_func

    return decorator


def dispatch_event(event: Event) -> List[Any]:
    """Dispatch event synchronously to all registered handlers.

    All handlers for the event type are called in order. If a handler
    raises an exception, it is caught and logged, but processing
    continues with remaining handlers.

    Args:
        event: The event to dispatch.

    Returns:
        List of return values from all handlers.
    """
    results = []
    handlers = EVENT_HANDLERS.get(event.event_type, [])

    logger.info(
        "dispatching_event",
        event_type=event.event_type,
        handler_count=len(handlers),
        correlation_id=str(event.correlation_id),
    )

    for handler in handlers:
        try:
            result = handler(event)
            results.append(result)
        except Exception as e:
            handler_name = getattr(handler, "__name__", "unknown")
            logger.error(
                "event_handler_failed",
                handler=handler_name,
                event_type=event.event_type,
                error=str(e),
                correlation_id=str(event.correlation_id),
            )

    return results


def _background_worker(evt: Event) -> None:
    """Worker wrapper to call dispatch_event and log exceptions."""
    try:
        dispatch_event(evt)
    except Exception as e:
        logger.exception(
            "background_event_dispatch_failed",
            event_type=evt.event_type,
            error=str(e),
            correlation_id=str(evt.correlation_id),
        )


def _get_or_create_executor(max_workers: int = 4) -> Optional[ThreadPoolExecutor]:
    """Lazily create the module-scoped executor if needed.

    Returns None when the executor has been explicitly shut down.

    Args:
        max_workers: Maximum number of worker threads.

    Returns:
        ThreadPoolExecutor instance or None if shutdown.
    """
    global _EXECUTOR
    with _executor_lock:
        if _executor_shutdown:
            return None
        if _EXECUTOR is None:
            _EXECUTOR = ThreadPoolExecutor(max_workers=max_workers)
            logger.debug("created_background_event_executor", max_workers=max_workers)
        return _EXECUTOR


def start_event_executor(max_workers: int = 4) -> None:
    """Explicitly start the background executor (optional).

    Args:
        max_workers: Maximum number of worker threads.
    """
    _get_or_create_executor(max_workers=max_workers)


def shutdown_event_executor(wait: bool = True) -> None:
    """Shut down the background executor and prevent further submissions.

    This function is idempotent and can be called safely multiple times.

    Args:
        wait: If True, wait for pending tasks to complete.
    """
    global _EXECUTOR, _executor_shutdown
    with _executor_lock:
        if _EXECUTOR is None:
            _executor_shutdown = True
            return
        try:
            _EXECUTOR.shutdown(wait=wait)
            logger.debug("background_event_executor_shut_down", wait=wait)
        finally:
            _EXECUTOR = None
            _executor_shutdown = True


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
    try:
        executor = _get_or_create_executor()
        if executor is None:
            logger.error(
                "event_executor_unavailable",
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
            )
            return
        executor.submit(_background_worker, event)
    except Exception:
        logger.exception(
            "failed_to_submit_event_to_executor",
            event_type=event.event_type,
            correlation_id=str(event.correlation_id),
        )


def get_registered_events() -> List[str]:
    """Get list of all registered event types.

    Returns:
        List of event type strings.
    """
    return list(EVENT_HANDLERS.keys())


def get_handlers_for_event(event_type: str) -> List[Callable]:
    """Get all handlers registered for a specific event type.

    Args:
        event_type: The event type to query.

    Returns:
        List of handler functions.
    """
    return EVENT_HANDLERS.get(event_type, [])


def clear_handlers() -> None:
    """Clear all registered handlers.

    WARNING: This is intended for testing only.
    """
    EVENT_HANDLERS.clear()
    logger.debug("cleared_all_event_handlers")
