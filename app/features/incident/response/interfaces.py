"""The Protocols the response services depend on beyond core's, implemented in ``adapters/``."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from capabilities.oncall.api import OnCallPerson
from contracts.coordination import ClaimOutcome
from features.incident.core.api import (
    ConversationReference,
    Incident,
    MessageReference,
    ReportReference,
    VideoCallReference,
)


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


class Claims(Protocol):
    """Async claims over the idempotency primitive (decisions/reliability.md): claim a key, then complete or release it.

    ``claim`` returns NEW with a token, COMPLETED with the stored outcome, or
    IN_PROGRESS while another execution holds the key; a store that cannot tell
    is IN_PROGRESS (fail closed). ``complete`` and ``release`` apply only while
    the token holds the key and say so.
    """

    async def claim(self, key: str) -> ClaimOutcome:
        """Claim ``key``; the token is set exactly when the result is NEW."""
        ...

    async def complete(self, key: str, outcome: dict[str, Any], claim_token: str) -> bool:
        """Record ``outcome`` under ``key``; False, writing nothing, when the token no longer holds it."""
        ...

    async def release(self, key: str, claim_token: str) -> bool:
        """Free an in-progress claim so a retry can run; False when the token does not hold it."""
        ...


class DeclareTexts(Protocol):
    """The declare's words, rendered by the caller (locale, platform markup); the service chooses none of them."""

    def topic(self, incident: Incident) -> str:
        """The conversation's topic."""
        ...

    def purpose(self, incident: Incident) -> str:
        """The conversation's purpose (description)."""
        ...

    def canvas(self, incident: Incident) -> str:
        """The markdown the conversation's canvas starts from."""
        ...

    def announcement(self, incident: Incident, conversation: ConversationReference) -> str:
        """The announcement posted in the announcement channel, naming the incident's conversation."""
        ...

    def severity_warning(self, incident: Incident) -> str | None:
        """The warning posted when the incident is declared with a severity; ``None`` when there is none."""
        ...

    def report_bookmark(self) -> str:
        """The report bookmark's title."""
        ...

    def report_posted(self, report: ReportReference) -> str:
        """The message that links the new report."""
        ...

    def report_placeholders(
        self, incident: Incident, conversation: ConversationReference | None, on_call: tuple[OnCallPerson, ...]
    ) -> Mapping[str, str]:
        """The new report's placeholder values (case-sensitive keys)."""
        ...

    def video_call_bookmark(self) -> str:
        """The video call bookmark's title."""
        ...

    def video_call_posted(self, call: VideoCallReference) -> str:
        """The message that links the new video call."""
        ...

    def source_alert_bookmark(self) -> str:
        """The source alert bookmark's title."""
        ...

    def source_alert_posted(self, alert: MessageReference) -> str:
        """The message that links the alert the incident was declared from."""
        ...

    def on_call_unavailable(self, incident: Incident) -> str:
        """The message saying nobody on call was invited (no schedule, or the source failed)."""
        ...

    def next_steps(self, incident: Incident) -> str:
        """The closing message listing what responders do next."""
        ...
