"""Audit handler for event system.

Writes events to Sentinel for compliance and audit trail.
"""

from core.logging import get_module_logger
from infrastructure.events.models import Event
from integrations.sentinel import client as sentinel_client

logger = get_module_logger()


class AuditHandler:
    """Handles audit trail writing for events."""

    def __init__(self, sentinel_client_override=None):
        """Initialize audit handler.

        Args:
            sentinel_client_override: Override sentinel client (for testing).
        """
        self.sentinel_client = sentinel_client_override or sentinel_client

    def handle(self, event: Event) -> None:
        """Handle event by writing to audit trail.

        Args:
            event: The event to audit.
        """
        try:
            logger.info(
                "writing_event_to_audit",
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
                user=event.user_email,
            )

            self.sentinel_client.log_to_sentinel(
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
                user=event.user_email,
                metadata=event.metadata,
                timestamp=event.timestamp.isoformat(),
            )
        except Exception as e:
            logger.error(
                "failed_to_write_audit_entry",
                event_type=event.event_type,
                error=str(e),
                correlation_id=str(event.correlation_id),
            )
