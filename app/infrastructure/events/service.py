"""Event dispatcher service for dependency injection.

Provides a class-based interface to the event system for easier DI and testing.
"""

from typing import Any, Callable, List

from infrastructure.events.models import Event
from infrastructure.events.dispatcher import (
    dispatch_event,
    dispatch_background,
    register_event_handler,
    start_event_executor,
    shutdown_event_executor,
    get_registered_events,
    get_handlers_for_event,
)


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

    def dispatch(self, event: Event) -> List[Any]:
        """Dispatch event synchronously to all registered handlers.

        Args:
            event: Event to dispatch

        Returns:
            List of return values from all handlers
        """
        return dispatch_event(event)

    def dispatch_background(self, event: Event) -> None:
        """Dispatch event asynchronously in background thread.

        Fire-and-forget semantics. Exceptions are caught and logged.

        Args:
            event: Event to dispatch
        """
        dispatch_background(event)

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
        return register_event_handler(event_type)

    def start_executor(self, max_workers: int = 4) -> None:
        """Start the background thread pool executor.

        Args:
            max_workers: Maximum number of worker threads
        """
        start_event_executor(max_workers=max_workers)

    def shutdown_executor(self, wait: bool = True) -> None:
        """Shutdown the background executor.

        Args:
            wait: If True, wait for pending tasks to complete
        """
        shutdown_event_executor(wait=wait)

    def get_registered_events(self) -> List[str]:
        """Get list of all registered event types.

        Returns:
            List of event type strings
        """
        return get_registered_events()

    def get_handlers_for_event(self, event_type: str) -> List[Callable]:
        """Get all handlers registered for a specific event type.

        Args:
            event_type: Event type to query

        Returns:
            List of handler functions
        """
        return get_handlers_for_event(event_type)
