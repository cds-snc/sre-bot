"""Domain types every incident subdomain works on."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TranscriptMessage:
    """One message of an incident conversation, as a person would read it.

    Attributes:
        author: Display name of the person or bot that posted the message.
        text: Message text, stripped of surrounding whitespace.
        posted_at: When the message was posted, timezone-aware UTC. ``None``
            when the platform gave no usable time. Formatting it for display is
            the consumer's job.
    """

    author: str
    text: str
    posted_at: datetime | None = None
