"""What the capability tells a destination: platform-neutral message intents.

The core decides what to say (wording in the destination's languages, the sender's details
once, the actions consumers offer); each platform's poster decides how to show it, and
escapes every value for its own format (decisions/platform-transports.md: outbound
messages are intents).
"""

import json
from dataclasses import dataclass

from capabilities.webhooks.domain.events import Alert, InboundEvent, JsonDocument, Link, Notification
from capabilities.webhooks.domain.extensions import EventAction
from capabilities.webhooks.domain.values import neutralise_text, truncate
from contracts.languages import MultilingualText


@dataclass(frozen=True)
class ChannelMessage:
    """An alert or notification to post.

    ``title``, ``summary`` and the link labels are the bot's wording, in the destination's
    languages and order; ``details`` is the sender's own text, shown once; ``mentions`` lets a
    platform turn email addresses in the summary and details into mentions.
    """

    title: MultilingualText
    summary: MultilingualText
    details: str | None = None
    links: tuple[Link, ...] = ()
    actions: tuple[EventAction, ...] = ()
    mentions: bool = False


@dataclass(frozen=True)
class FallbackMessage:
    """What an unmatched delivery or a render failure posts.

    ``header`` is the bot's wording, one part per language; ``source`` is the instance's
    name and ``body`` the decoded message as text, both shown once and never translated.
    """

    header: MultilingualText
    source: str
    body: str


type OutboundMessage = ChannelMessage | FallbackMessage


def channel_message(event: InboundEvent, *, actions: tuple[EventAction, ...] = (), mentions: bool = False) -> ChannelMessage:
    """The message for an alert or notification event; any other type has no channel message."""
    data = event.data
    if not isinstance(data, Alert | Notification):
        raise ValueError(f"event type {event.type} has no channel message")
    return ChannelMessage(
        title=data.title, summary=data.summary, details=data.details, links=data.links, actions=actions, mentions=mentions
    )


def fallback_body(decoded: JsonDocument, limit: int) -> str:
    """The decoded message as compact JSON text, neutralised and cut to ``limit`` characters.

    The platform adapter escapes it and fits it again to its own limits after escaping.
    """
    text = neutralise_text(json.dumps(decoded, ensure_ascii=False, separators=(",", ":"), default=str))
    return truncate(text, limit)
