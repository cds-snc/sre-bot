"""Lightweight, feature-scoped event dispatcher for .groups.

Provides a tiny in-process registry and dispatcher used only by the
groups membership feature. Handlers register with
``@register_event_handler(event_type)`` and receive a single ``payload`` dict
when ``dispatch_event(event_type, payload)`` is called.

Note: this implementation is intentionally simple and feature-scoped. If we
need app-wide, cross-process, or durable delivery later we can move it to an
application-level service (for example, registered at FastAPI startup) or
replace it with an external broker/pub-sub solution.
"""

import atexit
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

from infrastructure.observability import get_module_logger

logger = get_module_logger()

# Event handler registry
EVENT_HANDLERS: Dict[str, List[Callable]] = {}

# Managed executor for background dispatches. It is created lazily and can
# be shut down explicitly via `shutdown_event_executor`. Keep it
# module-scoped to limit thread growth for the feature.
_EXECUTOR: Optional[ThreadPoolExecutor] = None
_executor_lock = Lock()
# Track whether the executor has been shut down to prevent late submissions
_executor_shutdown = False


def register_event_handler(event_type: str):
    """Decorator to register an event handler for a specific event type."""

    def decorator(handler_func: Callable):
        if event_type not in EVENT_HANDLERS:
            EVENT_HANDLERS[event_type] = []
        EVENT_HANDLERS[event_type].append(handler_func)
        logger.debug(
            f"Registered handler {handler_func.__name__} for event {event_type}"
        )
        return handler_func

    return decorator


def dispatch_event(event_type: str, payload: Dict[str, Any]) -> List[Any]:
    """Dispatch an event to all registered handlers."""
    results = []
    handlers = EVENT_HANDLERS.get(event_type, [])

    logger.info(f"Dispatching event {event_type} to {len(handlers)} handlers")

    for handler in handlers:
        try:
            result = handler(payload)
            results.append(result)
        except Exception as e:
            logger.error(
                f"Error in event handler {handler.__name__} for event {event_type}: {e}"
            )
            # Continue processing other handlers despite the error

    return results


def _background_worker(evt: str, p: Dict[str, Any]) -> None:
    """Worker wrapper to call dispatch_event and log exceptions."""
    try:
        dispatch_event(evt, p)
    except Exception as e:  # pragma: no cover - defensive logging
        logger.exception(
            "background_event_dispatch_failed", service_event=evt, error=str(e)
        )


def _get_or_create_executor(max_workers: int = 4) -> Optional[ThreadPoolExecutor]:
    """Lazily create the module-scoped executor if needed.

    Returns None when the executor has been explicitly shut down.
    """
    global _EXECUTOR
    with _executor_lock:
        if _executor_shutdown:
            return None
        if _EXECUTOR is None:
            _EXECUTOR = ThreadPoolExecutor(max_workers=max_workers)
            logger.debug("created background event executor", max_workers=max_workers)
        return _EXECUTOR


def start_event_executor(max_workers: int = 4) -> None:
    """Explicitly start the background executor (optional)."""
    _get_or_create_executor(max_workers=max_workers)


def shutdown_event_executor(wait: bool = True) -> None:
    """Shut down the background executor and prevent further submissions.

    This function is idempotent.
    """
    global _EXECUTOR, _executor_shutdown
    with _executor_lock:
        if _EXECUTOR is None:
            _executor_shutdown = True
            return
        try:
            _EXECUTOR.shutdown(wait=wait)
            logger.debug("background event executor shut down", wait=wait)
        finally:
            _EXECUTOR = None
            _executor_shutdown = True


@atexit.register
def _atexit_shutdown():
    # Best-effort shutdown at process exit
    try:
        shutdown_event_executor(wait=False)
    except Exception:
        # Avoid raising during interpreter shutdown
        pass


def dispatch_background(event_type: str, payload: Dict[str, Any]) -> None:
    """Submit a background dispatch to the internal executor.

    This is a convenience for callers that want fire-and-forget semantics.
    Any exceptions thrown by handlers are caught and logged inside the
    worker so callers are not affected. If the executor has been shut down
    submissions are ignored and an error is logged.
    """
    try:
        executor = _get_or_create_executor()
        if executor is None:
            logger.error("event_executor_unavailable", service_event=event_type)
            return
        executor.submit(_background_worker, event_type, payload)
    except Exception:  # pragma: no cover - very defensive
        logger.exception("failed_to_submit_event_to_executor", service_event=event_type)


def get_registered_events() -> List[str]:
    """Get list of all registered event types."""
    return list(EVENT_HANDLERS.keys())


def get_handlers_for_event(event_type: str) -> List[Callable]:
    """Get all handlers registered for a specific event type."""
    return EVENT_HANDLERS.get(event_type, [])
