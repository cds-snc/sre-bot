"""Public surface of the Webhooks capability: its domain types.

Features import this module only (decisions/plugin-architecture.md). The extension point
that lets a feature consume events arrives with the capability's hookspecs.
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
from capabilities.webhooks.domain.kinds import AuthTier, Destination, Owner, SenderKind, WebhookInstance

__all__ = [
    "Alert",
    "AlertStatus",
    "AuthTier",
    "Destination",
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
