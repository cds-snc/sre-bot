"""Public surface of the incident core package.

Subdomains of the incident feature import this module and nothing else from
``core``: the interfaces every subdomain works on, their domain types and the
provider functions that resolve the default implementations.
"""

from collections.abc import Sequence
from datetime import datetime
from functools import lru_cache
from typing import Protocol, runtime_checkable

from packages.incident.core.adapters.slack import build_incident_transcript_reader
from packages.incident.core.domain import TranscriptMessage

__all__ = ["IncidentTranscriptReader", "TranscriptMessage", "get_incident_transcript_reader"]


@runtime_checkable
class IncidentTranscriptReader(Protocol):
    """Interface reading what was said in an incident's conversation.

    Name resolution, ordering, time conversion and filtering happen behind the
    interface. Implementations never raise for a platform failure: they log it
    and return the documented empty value.
    """

    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        """Return when the conversation started, timezone-aware UTC.

        Returns ``None`` when the platform cannot say (the lookup failed or the
        conversation carries no creation time); the caller applies its own
        fallback window.
        """
        ...

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> Sequence[TranscriptMessage]:
        """Return the conversation's messages posted since ``since``, oldest first.

        Args:
            conversation_id: The conversation to read.
            since: Timezone-aware start of the window.
            limit: Maximum number of messages to fetch from the platform.
            exclude_own_and_system_messages: Drop this bot's own posts and the
                platform's system events (joins, topic changes and the like).

        Returns:
            The messages in chronological order; empty on a platform failure.
        """
        ...


@lru_cache(maxsize=1)
def get_incident_transcript_reader() -> IncidentTranscriptReader:
    """Return the process-wide Slack-backed ``IncidentTranscriptReader``."""
    return build_incident_transcript_reader()
