"""The postmortem meeting scheduled event sent to Sentinel through the legacy client.

TODO(TASK-122): move onto the audit capability's sink, with the Logs Ingestion API
rebuild. The event keeps the legacy name ``incident_retro_scheduled``
so Sentinel queries keyed on ``event`` keep working; it is sent once per booked or
recreated meeting (the legacy sent it when the button was pressed, with the whole
request body), and the message holds only the incident, conversation, user,
meeting and time (decisions/observability.md).
"""

import asyncio

from features.incident.postmortem.interfaces import MeetingScheduledEvent
from integrations.sentinel.client import log_to_sentinel

RETRO_SCHEDULED = "incident_retro_scheduled"


class SentinelPostmortemEventSink:
    """Send the event with ``log_to_sentinel``, which logs a failed send and never raises."""

    async def send_meeting_scheduled(self, event: MeetingScheduledEvent) -> None:
        """Send ``incident_retro_scheduled`` with the minimal message, off the event loop."""
        message = {
            "incident_id": event.incident_id,
            "conversation_id": event.conversation_id,
            "user_id": event.user_id,
            "meeting_id": event.meeting_id,
            "at": event.at.isoformat(),
        }
        await asyncio.to_thread(log_to_sentinel, RETRO_SCHEDULED, message)
