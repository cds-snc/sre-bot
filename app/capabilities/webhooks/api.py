"""Public surface of the Webhooks capability: its domain types.

Features import this module only (decisions/plugin-architecture.md). A feature consumes
events through the capability's extension point (``hookspecs.py``): it returns its
``EventConsumer`` and ``EventHandler`` values from the hooks there.
"""

from capabilities.webhooks.domain.events import (
    Alert,
    AlertStatus,
    EventType,
    FieldValue,
    InboundEvent,
    Link,
    Notification,
    Severity,
    SlackPassthrough,
)
from capabilities.webhooks.domain.extensions import EventAction, EventConsumer, EventContext, EventHandler
from capabilities.webhooks.domain.kinds import AuthTier, Destination, Owner, SenderKind, WebhookInstance

__all__ = [
    "Alert",
    "AlertStatus",
    "AuthTier",
    "Destination",
    "EventAction",
    "EventConsumer",
    "EventContext",
    "EventHandler",
    "EventType",
    "FieldValue",
    "InboundEvent",
    "Link",
    "Notification",
    "Owner",
    "SenderKind",
    "Severity",
    "SlackPassthrough",
    "WebhookInstance",
]
