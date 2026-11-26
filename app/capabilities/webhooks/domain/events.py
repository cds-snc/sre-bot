"""The canonical inbound event and its event types (decisions/webhooks.md 5a Canonical model).

``InboundEvent`` uses the CloudEvents 1.0 context attribute names. Its ``type`` is set by the
matched sender kind, never read from the payload, and its ``data`` is the event type's body,
built only from the kind's validated extracted fields and its rendered templates.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from contracts.languages import MultilingualText

type Scalar = str | int | float | bool
type FieldValue = Scalar | tuple[Scalar, ...] | None
# A decoded JSON body: an object or an array, never text that a query library would parse again.
type JsonDocument = Mapping[str, Any] | list[Any]

LOCAL_EVENT_ID_PREFIX = "local:"


class EventType(StrEnum):
    """The event types the capability defines; features may register more."""

    ALERT = "alert"
    NOTIFICATION = "notification"
    SLACK_PASSTHROUGH = "slack.passthrough"


class AlertStatus(StrEnum):
    """An alert's state; carried but unused until update-on-resolve exists."""

    FIRING = "firing"
    RESOLVED = "resolved"
    INFO = "info"


class Severity(StrEnum):
    """An alert's severity, on the PagerDuty Events v2 scale."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Link:
    """A link the event offers: a validated https URL and its label in the message's languages."""

    url: str
    label: MultilingualText


def _frozen(attributes: Mapping[str, FieldValue]) -> Mapping[str, FieldValue]:
    return MappingProxyType(dict(attributes))


@dataclass(frozen=True)
class Notification:
    """Information to show, with no triage.

    ``title``, ``summary`` and the link labels are the bot's wording, one part per language;
    ``details`` is the sender's own text, in its source language, shown once.
    """

    title: MultilingualText
    summary: MultilingualText
    details: str | None = None
    links: tuple[Link, ...] = ()
    attributes: Mapping[str, FieldValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _frozen(self.attributes))


@dataclass(frozen=True)
class Alert:
    """A condition someone may need to act on; ``status`` and ``dedup_key`` are carried for later use."""

    title: MultilingualText
    summary: MultilingualText
    status: AlertStatus = AlertStatus.FIRING
    severity: Severity | None = None
    dedup_key: str | None = None
    details: str | None = None
    links: tuple[Link, ...] = ()
    attributes: Mapping[str, FieldValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _frozen(self.attributes))


@dataclass(frozen=True)
class SlackPassthrough:
    """A Slack-shaped message from the legacy protocol: opaque, Slack-only and hardened before posting."""

    message: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "message", MappingProxyType(dict(self.message)))


type EventData = Alert | Notification | SlackPassthrough


@dataclass(frozen=True)
class InboundEvent:
    """One inbound event, named after the CloudEvents 1.0 context attributes.

    Attributes:
        id: The protocol's delivery id, or ``local:<uuid>`` when the protocol has none.
        source: The instance's ``instance_ref``, never the URL token.
        type: Set by the matched sender kind.
        time: When the delivery was received.
        data: The event type's body.
        subject: Optional subject of the event.
    """

    id: str
    source: str
    type: EventType
    time: datetime
    data: EventData
    subject: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.source:
            raise ValueError("an event needs an id and a source")
        if self.time.tzinfo is None:
            raise ValueError("an event's time must be timezone-aware")
        expected = {
            EventType.ALERT: Alert,
            EventType.NOTIFICATION: Notification,
            EventType.SLACK_PASSTHROUGH: SlackPassthrough,
        }[self.type]
        if not isinstance(self.data, expected):
            raise ValueError(f"an event of type {self.type} carries {expected.__name__} data")


def local_event_id() -> str:
    """Return a server-generated event id, for a protocol that gives no delivery id."""
    return f"{LOCAL_EVENT_ID_PREFIX}{uuid.uuid4()}"
