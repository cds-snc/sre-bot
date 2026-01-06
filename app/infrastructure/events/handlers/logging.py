"""Logging handler for event system.

Writes events to structured logs.
"""

import structlog
from infrastructure.events.models import Event

logger = structlog.get_logger()


class LoggingHandler:
    """Handles structured logging for events."""

    def handle(self, event: Event) -> None:
        """Handle event by logging with structured fields.

        Args:
            event: The event to log.
        """
        try:
            logger.info(
                "event_occurred",
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
                user=event.user_email,
                metadata=event.metadata,
                timestamp=event.timestamp.isoformat(),
            )
        except Exception as e:
            logger.error(
                "failed_to_log_event",
                event_type=event.event_type,
                error=str(e),
                correlation_id=str(event.correlation_id),
            )
