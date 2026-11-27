"""The response events sent to Sentinel through the legacy client: the archived event and the declare's events.

TODO(TASK-122): moves onto the audit capability's sink, with TASK-171's Logs
Ingestion API rebuild. Until then each event keeps the legacy envelope
``{event, message}`` so Sentinel queries keyed on ``event`` keep working, and the
message holds only ids and times, never the request body (decisions/observability.md).
"""

import asyncio
from collections.abc import Mapping

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


class SentinelDeclareEventSink:
    """Send a declare event (the form submitted, an alert button pressed) with ``log_to_sentinel``; never raises."""

    async def send(self, event: str, message: Mapping[str, str]) -> None:
        """Send ``event`` with its ids-only ``message``, off the event loop."""
        await asyncio.to_thread(log_to_sentinel, event, dict(message))
