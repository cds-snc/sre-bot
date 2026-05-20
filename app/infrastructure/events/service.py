"""Blinker-backed event dispatcher facade.

Provides error-isolated in-process event dispatch with a DI-friendly API.
"""

from concurrent.futures import ThreadPoolExecutor
from functools import cache
from threading import Lock
from typing import Any, Callable

import blinker
import structlog

from infrastructure.events.models import Event

logger = structlog.get_logger()


class EventDispatcher:
    """Event dispatcher that wraps blinker signals behind a stable facade."""

    def __init__(self) -> None:
        self._namespace = blinker.Namespace()
        self._executor: ThreadPoolExecutor | None = None
        self._executor_lock = Lock()
        self._executor_shutdown = False

    def _get_signal(self, event_type: str) -> blinker.NamedSignal:
        """Get or create a signal for the event type."""
        return self._namespace.signal(event_type)

    def register_handler(
        self, event_type: str, handler: Callable[[Event], Any]
    ) -> None:
        """Register a handler for an event type."""
        signal = self._get_signal(event_type)
        signal.connect(handler, weak=False)

        handler_name = getattr(handler, "__name__", repr(handler))
        log = logger.bind(handler=handler_name, event_type=event_type)
        log.info(
            "event_handler_registered",
            handler_count=len(list(signal.receivers_for(blinker.ANY))),
        )

    def dispatch(self, event: Event) -> None:
        """Dispatch synchronously with per-handler error isolation."""
        signal = self._get_signal(event.event_type)
        log = logger.bind(
            event_type=event.event_type,
            correlation_id=str(event.correlation_id),
        )

        receivers = list(signal.receivers_for(blinker.ANY))
        log.info("dispatching_event", handler_count=len(receivers))

        for receiver in receivers:
            try:
                receiver(event)
            except Exception:
                handler_name = getattr(receiver, "__name__", repr(receiver))
                log.exception("event_handler_failed", handler=handler_name)

    def dispatch_background(self, event: Event) -> None:
        """Submit dispatch work to the background executor."""
        executor = self._get_or_create_executor()
        if executor is None:
            log = logger.bind(
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
            )
            log.error("event_executor_unavailable")
            return

        try:
            executor.submit(self._background_worker, event)
        except Exception:
            log = logger.bind(
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
            )
            log.exception("failed_to_submit_event_to_executor")

    def _background_worker(self, event: Event) -> None:
        """Worker that reuses synchronous dispatch behavior."""
        self.dispatch(event)

    def _get_or_create_executor(
        self, max_workers: int = 4
    ) -> ThreadPoolExecutor | None:
        """Lazily create the background executor unless shutdown was requested."""
        with self._executor_lock:
            if self._executor_shutdown:
                return None
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=max_workers)
                logger.debug(
                    "created_background_event_executor",
                    max_workers=max_workers,
                )
            return self._executor

    def start_executor(self, max_workers: int = 4) -> None:
        """Explicitly start the background executor."""
        self._get_or_create_executor(max_workers=max_workers)

    def shutdown_executor(self, wait: bool = True) -> None:
        """Shut down the background executor. Idempotent."""
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

    def get_registered_event_types(self) -> list[str]:
        """Get event types that currently have at least one handler."""
        return [
            name
            for name, signal in self._namespace.items()
            if list(signal.receivers_for(blinker.ANY))
        ]

    def get_handler_count(self, event_type: str) -> int:
        """Get number of handlers registered for an event type."""
        signal = self._get_signal(event_type)
        return len(list(signal.receivers_for(blinker.ANY)))


@cache
def get_event_dispatcher() -> EventDispatcher:
    """Get application-scoped event dispatcher singleton.
    Returns:
        EventDispatcher: Cached event dispatcher instance
    """
    return EventDispatcher()
