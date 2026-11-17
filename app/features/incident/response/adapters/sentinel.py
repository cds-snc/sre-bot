"""The archived event sent to Sentinel through the legacy client.

TODO(TASK-122): moves onto the audit capability's sink, with TASK-171's Logs
Ingestion API rebuild. Until then the event keeps the legacy envelope
``{event, message}`` so Sentinel queries keyed on ``event`` keep working, and the
message holds only the incident, conversation, user and time, never the request
body (decisions/observability.md).
"""

import asyncio

from features.incident.response.interfaces import ArchivedEvent
from integrations.sentinel.client import log_to_sentinel

CHANNEL_ARCHIVED = "incident_channel_archived"


class SentinelArchiveEventSink:
    """Send the archived event with ``log_to_sentinel``, which logs a failed send and never raises."""

    async def send_channel_archived(self, event: ArchivedEvent) -> None:
        """Send ``incident_channel_archived`` with the minimal message, off the event loop."""
        message = {
            "incident_id": event.incident_id,
            "conversation_id": event.conversation_id,
            "user_id": event.user_id,
            "at": event.at.isoformat(),
        }
        await asyncio.to_thread(log_to_sentinel, CHANNEL_ARCHIVED, message)
