"""Event dispatcher service for dependency injection.

Provides a class-based interface to the event system for easier DI and testing.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Callable

import structlog

from infrastructure.events.models import Event
from infrastructure.events.registry import EventHandlerRegistry, get_event_registry

logger = structlog.get_logger()


class EventDispatcher:
    """Class-based event dispatcher service.

    Wraps the module-level event functions in a class interface to support
    dependency injection and easier testing with mocks.

    This is a thin facade - all actual work is delegated to the module-level
    functions in infrastructure.events.dispatcher.

    Usage:
        # Via dependency injection
        from infrastructure.services import EventDispatcherDep

        @router.post("/action")
        def perform_action(dispatcher: EventDispatcherDep):
            event = Event(event_type="action.performed", user_email="user@example.com")
            dispatcher.dispatch(event)

        # Direct instantiation
        from infrastructure.events import EventDispatcher

        dispatcher = EventDispatcher()
        dispatcher.dispatch(event)
    """

    def __init__(self, registry: EventHandlerRegistry | None = None) -> None:
        self._registry = registry or get_event_registry()
        self._executor: ThreadPoolExecutor | None = None
        self._executor_lock = Lock()
        self._executor_shutdown = False

    def dispatch(self, event: Event) -> list[Any]:
        """Dispatch event synchronously to all registered handlers.

        Args:
            event: Event to dispatch

        Returns:
            List of return values from all handlers
        """
        results = []
        handlers = self._registry.get_handlers(event.event_type)

        log = logger.bind(
            event_type=event.event_type,
            correlation_id=str(event.correlation_id),
        )
        log.info("dispatching_event", handler_count=len(handlers))

        for handler in handlers:
            try:
                results.append(handler(event))
            except Exception as exc:  # pragma: no cover - defensive logging
                handler_name = getattr(handler, "__name__", "unknown")
                log.error(
                    "event_handler_failed",
                    handler=handler_name,
                    error=str(exc),
                )

        return results

    def dispatch_background(self, event: Event) -> None:
        """Dispatch event asynchronously in background thread.

        Fire-and-forget semantics. Exceptions are caught and logged.

        Args:
            event: Event to dispatch
        """
        try:
            executor = self._get_or_create_executor()
            if executor is None:
                log = logger.bind(
                    event_type=event.event_type,
                    correlation_id=str(event.correlation_id),
                )
                log.error("event_executor_unavailable")
                return
            executor.submit(self._background_worker, event)
        except Exception:  # pragma: no cover - defensive logging
            log = logger.bind(
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
            )
            log.exception("failed_to_submit_event_to_executor")

    def register_handler(self, event_type: str) -> Callable:
        """Decorator to register an event handler.

        Args:
            event_type: Type of event to handle (e.g., 'group.member.added')

        Returns:
            Decorator function that registers the handler

        Usage:
            dispatcher = EventDispatcher()

            @dispatcher.register_handler("my.event")
            def handle_my_event(event: Event):
                # Handle the event
                pass
        """

        def decorator(handler_func: Callable) -> Callable:
            self._registry.register(event_type, handler_func)
            handler_name = getattr(handler_func, "__name__", "unknown")
            log = logger.bind(handler=handler_name, event_type=event_type)
            log.debug(
                "registered_event_handler",
                total_handlers=len(self._registry.get_handlers_for_event(event_type)),
            )
            return handler_func

        return decorator

    def start_executor(self, max_workers: int = 4) -> None:
        """Start the background thread pool executor.

        Args:
            max_workers: Maximum number of worker threads
        """
        self._get_or_create_executor(max_workers=max_workers)

    def shutdown_executor(self, wait: bool = True) -> None:
        """Shutdown the background executor.

        Args:
            wait: If True, wait for pending tasks to complete
        """
        with self._executor_lock:
            if self._executor is None:
                self._executor_shutdown = True
                return
            try:
                self._executor.shutdown(wait=wait)
                logger.debug("background_event_executor_shut_down", wait=wait)
            finally:
                self._executor = None
                self._executor_shutdown = True

    def get_registered_events(self) -> list[str]:
        """Get list of all registered event types.

        Returns:
            List of event type strings
        """
        return self._registry.get_registered_events()

    def get_handlers_for_event(self, event_type: str) -> list[Callable]:
        """Get all handlers registered for a specific event type.

        Args:
            event_type: Event type to query

        Returns:
            List of handler functions
        """
        return self._registry.get_handlers_for_event(event_type)

    def clear_handlers(self) -> None:
        """Clear all handlers from the backing registry."""
        self._registry.clear()
        logger.debug("cleared_all_event_handlers")

    def _get_or_create_executor(
        self, max_workers: int = 4
    ) -> ThreadPoolExecutor | None:
        """Lazily create the internal executor unless shutdown was requested."""
        with self._executor_lock:
            if self._executor_shutdown:
                return None
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=max_workers)
                logger.debug(
                    "created_background_event_executor", max_workers=max_workers
                )
            return self._executor

    def _background_worker(self, event: Event) -> None:
        """Run synchronous dispatch in a worker thread and log failures."""
        try:
            self.dispatch(event)
        except Exception as exc:  # pragma: no cover - defensive logging
            log = logger.bind(
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
            )
            log.exception("background_event_dispatch_failed", error=str(exc))
