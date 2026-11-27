"""Interpret a decoded delivery: match a kind, extract its fields, render the event.

Matching and rendering are separate stages, so a match never renders nothing by accident:
a kind that should post nothing says ``suppress``. The payload never chooses the event's
type: the matched kind does (decisions/webhooks.md Three layers, Canonical model).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from capabilities.webhooks.domain.events import InboundEvent, JsonDocument
from capabilities.webhooks.domain.extraction import ExtractionMiss, extract
from capabilities.webhooks.domain.kinds import SenderKind, first_match
from capabilities.webhooks.domain.limits import WebhookLimits
from capabilities.webhooks.domain.rendering import RenderFailure, render


@dataclass(frozen=True)
class Delivery:
    """What the interpret stage knows about a delivery besides its body."""

    event_id: str
    instance_ref: str
    instance_name: str
    received_at: datetime


@dataclass(frozen=True)
class Matched:
    """A kind matched and the event rendered."""

    kind: SenderKind
    event: InboundEvent


@dataclass(frozen=True)
class Suppressed:
    """A kind matched that posts nothing."""

    kind_id: str


@dataclass(frozen=True)
class Unmatched:
    """No kind of the instance matched: the delivery gets the fallback rendering."""


@dataclass(frozen=True)
class RenderFailed:
    """A kind matched but a required field was missing or a template failed."""

    kind_id: str
    field: str
    reason: str


type Interpretation = Matched | Suppressed | Unmatched | RenderFailed


def interpret(
    kinds: Sequence[SenderKind],
    document: JsonDocument,
    delivery: Delivery,
    *,
    languages: Sequence[str],
    limits: WebhookLimits,
) -> Interpretation:
    """Interpret ``document`` with the instance's ``kinds``, tried in their declared order."""
    kind = first_match(kinds, document)
    if kind is None:
        return Unmatched()
    if kind.suppress:
        return Suppressed(kind.id)
    fields = extract(kind, document, limits)
    if isinstance(fields, ExtractionMiss):
        return RenderFailed(kind.id, fields.field, fields.reason)
    try:
        data = render(
            kind,
            fields,
            instance_name=delivery.instance_name,
            received_at=delivery.received_at,
            languages=languages,
            limits=limits,
        )
    except RenderFailure as failure:
        return RenderFailed(failure.kind_id, failure.field, failure.reason)
    event = InboundEvent(
        id=delivery.event_id,
        source=delivery.instance_ref,
        type=kind.event_type,
        time=delivery.received_at,
        data=data,
    )
    return Matched(kind, event)
