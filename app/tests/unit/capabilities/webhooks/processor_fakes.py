"""Fakes and a builder for the webhook processor's tests and the ingress route's tests.

The inbox is the real ``RecordInboxStore`` over ``InMemoryRecordStore``, so dedupe and guards
behave as in production; posters, the language policy, the translator, the subscription
confirmer and the instance store are small recording stand-ins; the clock and the owner
tokens are deterministic.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from capabilities.webhooks.domain.events import EventType, InboundEvent
from capabilities.webhooks.domain.extensions import EventAction, EventContext
from capabilities.webhooks.domain.inbox import InboxItem, ItemKind, ProtocolDelivery, item_key
from capabilities.webhooks.domain.kinds import AuthTier, Destination, Owner, WebhookInstance
from capabilities.webhooks.domain.messages import OutboundMessage
from capabilities.webhooks.schemas import sender_kinds_content_kind
from capabilities.webhooks.service import RegisteredConsumer, WebhookExtensions, WebhookProcessor
from capabilities.webhooks.settings import get_webhooks_settings
from capabilities.webhooks.store import RecordInboxStore, inbox_table
from contracts.languages import MultilingualText
from contracts.operations import OperationResult, OperationStatus
from contracts.records import RecordStore
from contracts.workplace import WorkplaceSystem
from infrastructure.content.in_memory import InMemoryContentCatalogue
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.unit.capabilities.webhooks.conftest import build_kind, kind_document, payload

START = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
C1 = Destination(WorkplaceSystem.SLACK, "T1", "C1", triage=True)
C2 = Destination(WorkplaceSystem.SLACK, "T1", "C2")


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


class Session:
    def __init__(self, poster: Poster) -> None:
        self._poster = poster

    async def post(self, destination: Destination, message: OutboundMessage) -> OperationResult[str]:
        self._poster.posts.append((destination.conversation_id, message))
        if self._poster.delay:
            await asyncio.sleep(self._poster.delay)
        script = self._poster.script.get(destination.conversation_id)
        return script.pop(0) if script else OperationResult.success(data="ts")


@dataclass
class Poster:
    posts: list[tuple[str, OutboundMessage]] = field(default_factory=list)
    script: dict[str, list[OperationResult[str]]] = field(default_factory=dict)
    delay: float = 0.0
    sessions: int = 0

    def for_delivery(self) -> Session:
        self.sessions += 1
        return Session(self)


class Languages:
    def shared_languages(self, *, system: WorkplaceSystem, tenant: str, conversation_id: str) -> tuple[str, ...]:
        return ("en-US",)

    def reply_languages(self, user_locale: str | None) -> tuple[str, ...]:
        return ("en-US", "fr-FR")


class Translator:
    def translate(self, key: str, language: str, /, **variables: str) -> str:
        return f"{key}:{language}"


@dataclass
class Consumer:
    consumed: list[tuple[InboundEvent, EventContext]] = field(default_factory=list)
    failures: int = 0

    @property
    def event_types(self) -> frozenset[EventType]:
        return frozenset({EventType.ALERT})

    def actions(self, event: InboundEvent, languages: Any) -> tuple[EventAction, ...]:
        return (EventAction("incident.call", "v", MultilingualText.of(languages, lambda language: "Call")),)

    async def consume(self, event: InboundEvent, context: EventContext) -> None:
        if self.failures:
            self.failures -= 1
            raise RuntimeError("consumer down")
        self.consumed.append((event, context))


@dataclass
class Instances:
    instances: dict[str, WebhookInstance]

    async def by_url_id(self, webhook_id: str) -> OperationResult[WebhookInstance]:
        raise AssertionError("the processor never looks up by URL token")

    async def by_ref(self, instance_ref: str) -> OperationResult[WebhookInstance]:
        instance = self.instances.get(instance_ref)
        if instance is None:
            return OperationResult.error(OperationStatus.NOT_FOUND, "no such instance")
        return OperationResult.success(data=instance)


@dataclass
class Confirmer:
    results: list[OperationResult[None]] = field(default_factory=list)
    confirmed: list[str] = field(default_factory=list)

    async def confirm(self, subscribe_url: str) -> OperationResult[None]:
        self.confirmed.append(subscribe_url)
        return self.results.pop(0) if self.results else OperationResult.success()


def instance(**changes: Any) -> WebhookInstance:
    values: dict[str, Any] = {
        "instance_ref": "ref-1",
        "name": "budgets",
        "owner": Owner("sre", "sre@example.com"),
        "auth_tier": AuthTier.LEGACY,
        "protocol": "aws_sns",
        "sender_kinds": ("budget-alert",),
        "destinations": (C1, C2),
    }
    values.update(changes)
    return WebhookInstance(**values)


@dataclass
class World:
    processor: WebhookProcessor
    inbox: RecordInboxStore
    poster: Poster
    consumer: Consumer
    confirmer: Confirmer
    clock: Clock
    instances: Instances

    async def item(self, delivery_id: str = "m-1", instance_ref: str = "ref-1") -> InboxItem:
        result = await self.inbox.get(item_key(instance_ref, delivery_id))
        assert result.data is not None
        return result.data


def world(
    *, instance_: WebhookInstance | None = None, jitter: Callable[[], float] = lambda: 1.0, records: RecordStore | None = None
) -> World:
    catalogue = InMemoryContentCatalogue()
    catalogue.add(sender_kinds_content_kind(), "budget-alert", build_kind(kind_document()))
    poster, consumer, confirmer, clock = Poster(), Consumer(), Confirmer(), Clock()
    instances = Instances({"ref-1": instance_ or instance()})
    inbox = RecordInboxStore(records or InMemoryRecordStore(), inbox_table("inbox"))
    tokens = iter(f"token-{n}" for n in range(1000))
    extensions = WebhookExtensions(
        consumers=MappingProxyType({EventType.ALERT: (RegisteredConsumer("incident", consumer),)}),
        handlers=MappingProxyType({}),
        service_scopes=object(),
    )
    processor = WebhookProcessor(
        inbox=inbox,
        instances=instances,
        catalogue=catalogue,
        languages=Languages(),
        translator=Translator(),
        extensions=extensions,
        posters={WorkplaceSystem.SLACK: poster},
        confirmer=confirmer,
        settings=get_webhooks_settings(),
        clock=clock,
        new_token=lambda: next(tokens),
        jitter=jitter,
    )
    return World(processor, inbox, poster, consumer, confirmer, clock, instances)


def delivery(delivery_id: str = "m-1", document: Any = None, kind: ItemKind = ItemKind.EVENT, **extra: Any) -> ProtocolDelivery:
    return ProtocolDelivery(delivery_id=delivery_id, kind=kind, document=payload() if document is None else document, **extra)
