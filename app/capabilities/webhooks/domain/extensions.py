"""What features contribute to the webhooks capability (decisions/webhooks.md 5a Extension point).

Consumers by event type and handlers by id, collected once at startup. The contracts are
platform-neutral: a consumer offers actions as wording and ids, each platform's poster
renders them, and a click lands on the consumer's own platform entrypoint.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from capabilities.webhooks.domain.events import EventType, InboundEvent
from contracts.languages import MultilingualText
from contracts.services import ServiceScopeOpener


@dataclass(frozen=True)
class EventAction:
    """An action a consumer offers on a posted event (a triage button).

    ``action_id`` starts with the contributing plugin's entry-point name and a dot, so a
    click reaches that plugin's handler only; ``value`` is what the click carries back;
    ``label`` is the bot's wording, one part per language.
    """

    action_id: str
    value: str
    label: MultilingualText

    def __post_init__(self) -> None:
        if not self.action_id or not self.value:
            raise ValueError("an action needs an id and a value")


@dataclass(frozen=True)
class EventContext:
    """What a consumer or handler gets beside the event: the inbox item and a scope opener.

    The event itself carries the delivery id (``id``) and the instance (``source``);
    effects are keyed on the delivery id, so a redelivery never acts twice.
    """

    item_id: str
    service_scopes: ServiceScopeOpener


@runtime_checkable
class EventConsumer(Protocol):
    """Receives each event of its types once, and may offer actions on the posted message."""

    @property
    def event_types(self) -> frozenset[EventType]:
        """The event types this consumer receives."""
        ...

    def actions(self, event: InboundEvent, languages: Sequence[str]) -> tuple[EventAction, ...]:
        """Return the actions to offer on ``event``, worded in ``languages``; called only where triage applies."""
        ...

    async def consume(self, event: InboundEvent, context: EventContext) -> None:
        """Act on ``event``; opens its own scope from ``context.service_scopes``."""
        ...


@runtime_checkable
class EventHandler(Protocol):
    """Code a sender kind names with ``handler:``; it runs from the inbox item."""

    @property
    def handler_id(self) -> str:
        """The dotted id sender kinds name."""
        ...

    async def handle(self, event: InboundEvent, context: EventContext) -> None:
        """Act on ``event``; keyed on its delivery id so a redelivery cannot act twice."""
        ...
