"""The Protocols the response services depend on beyond core's, implemented in ``adapters/``."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ArchivedEvent:
    """The one event an archive sends: who archived which incident's conversation, and when."""

    incident_id: str
    conversation_id: str
    user_id: str
    at: datetime


class ArchiveEventSink(Protocol):
    """Where the archived event goes; a send failure is the sink's to log, never the archive's."""

    async def send_channel_archived(self, event: ArchivedEvent) -> None:
        """Send ``event``; never raises."""
        ...
