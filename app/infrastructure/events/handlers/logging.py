"""Logging handler for event system.

Writes events to structured logs.
"""

import structlog
from infrastructure.events.models import Event

logger = structlog.get_logger()


class LoggingHandler:
    """Handles structured logging for events."""

    def __init__(self):
        """Initialize logging handler with base logger."""
        self.log = logger.bind(component="logging_handler")

    def handle(self, event: Event) -> None:
        """Handle event by logging with structured fields.

        Args:
            event: The event to log.
        """
        log = self.log.bind(
            event_type=event.event_type,
            correlation_id=str(event.correlation_id),
            user=event.user_email,
        )
        try:
            log.info(
                "event_occurred",
                metadata=event.metadata,
                timestamp=event.timestamp.isoformat(),
            )
        except Exception as e:
            log.error("failed_to_log_event", error=str(e))
