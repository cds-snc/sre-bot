"""Webhooks application services: the extension point, ingest and processing.

``initialize_extensions`` runs once, in the host's extension-point phase. Every contributed
value comes from another plugin, so each is validated, and a bad one fails boot naming the
plugin. The returned ``WebhookExtensions`` is read at runtime; no pluggy hook is called after
startup (decisions/plugins.md).

``WebhookProcessor`` is the data plane after a protocol verified and decoded a delivery
(decisions/webhooks.md 3 Pipeline): it persists the item (the conditional insert is the
dedupe), processes it inline within the deadline, and leaves anything unfinished to the
sweeper. The inbox is the one retry point: a post is never retried in process, and a
platform's ``retry_after`` sets the item's next attempt (decisions/outbound-clients.md). Each
finished target is recorded on the item, so a retry repeats none of them.
"""

import asyncio
import json
import math
import random
import re
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from functools import partial
from types import MappingProxyType
from typing import Any

import structlog

from capabilities.webhooks.domain.events import EventType, InboundEvent, JsonDocument
from capabilities.webhooks.domain.extensions import EventAction, EventConsumer, EventContext, EventHandler
from capabilities.webhooks.domain.inbox import (
    InboxItem,
    ItemKind,
    ItemState,
    ProtocolDelivery,
    claimable,
    claimed,
    consume_target,
    finished,
    handler_target,
    new_item,
    next_retry_at,
    post_target,
    retry_scheduled,
    with_target_done,
)
from capabilities.webhooks.domain.interpret import Delivery, Matched, RenderFailed, Suppressed, Unmatched, interpret
from capabilities.webhooks.domain.kinds import Destination, InstanceState, SenderKind, WebhookInstance, resolve_kinds
from capabilities.webhooks.domain.messages import (
    FallbackMessage,
    OutboundMessage,
    PassthroughMessage,
    channel_message,
    fallback_body,
)
from capabilities.webhooks.interfaces import ChannelPoster, DeliveryPoster, InboxStore, SubscriptionConfirmer, WebhookStore
from capabilities.webhooks.schemas import HANDLER_ID_PATTERN, sender_kinds_content_kind
from capabilities.webhooks.settings import WebhooksSettings
from contracts.content import ContentCatalogue
from contracts.i18n.translator import Translator
from contracts.languages import LanguagePolicy, MultilingualText
from contracts.operations import OperationResult, OperationStatus
from contracts.plugins.extension_points import ExtensionPointContext
from contracts.services import ServiceScopeOpener
from contracts.workplace import WorkplaceSystem

logger = structlog.get_logger()

CONSUMERS_HOOK = "register_webhook_consumers"
HANDLERS_HOOK = "register_webhook_handlers"
# Event types a consumer may receive; slack.passthrough is opaque platform JSON with nothing typed to read.
CONSUMABLE_TYPES = frozenset({EventType.ALERT, EventType.NOTIFICATION})
_HANDLER_ID = re.compile(HANDLER_ID_PATTERN)
FALLBACK_HEADER_KEY = "webhooks.fallback.header"


class WebhookExtensionError(RuntimeError):
    """A contribution to the webhooks extension point is invalid; boot stops naming its source."""


@dataclass(frozen=True)
class RegisteredConsumer:
    """A consumer and the entry-point name of the plugin that contributed it."""

    plugin: str
    consumer: EventConsumer


@dataclass(frozen=True)
class WebhookExtensions:
    """The consumers and handlers collected at startup, read on every delivery."""

    consumers: Mapping[EventType, tuple[RegisteredConsumer, ...]]
    handlers: Mapping[str, EventHandler]
    service_scopes: ServiceScopeOpener

    def consumers_for(self, event_type: EventType) -> tuple[RegisteredConsumer, ...]:
        """The consumers of ``event_type``, in plugin load order."""
        return self.consumers.get(event_type, ())

    def handler(self, handler_id: str) -> EventHandler | None:
        """The handler a sender kind names, or None."""
        return self.handlers.get(handler_id)

    def actions_for(self, event: InboundEvent, languages: Sequence[str]) -> tuple[EventAction, ...]:
        """Gather the consumers' actions for ``event``; an action outside its plugin's namespace is dropped."""
        gathered: list[EventAction] = []
        for registered in self.consumers_for(event.type):
            for action in registered.consumer.actions(event, languages):
                if action.action_id.startswith(f"{registered.plugin}."):
                    gathered.append(action)
                else:
                    logger.warning("webhook_action_dropped", plugin=registered.plugin, reason="outside_namespace")
        return tuple(gathered)


def initialize_extensions(context: ExtensionPointContext) -> WebhookExtensions:
    """Collect and validate the contributions, then check the content's handler names against them."""
    consumers = _consumers(context.collect(CONSUMERS_HOOK))
    handlers = _handlers(context.collect(HANDLERS_HOOK))
    _check_kind_handlers(context.services.get(ContentCatalogue), handlers)
    return WebhookExtensions(
        consumers=MappingProxyType({event_type: tuple(entries) for event_type, entries in consumers.items()}),
        handlers=MappingProxyType(handlers),
        service_scopes=context.service_scopes,
    )


def _contributions(plugin: str, result: object, hook: str) -> Sequence[object]:
    if isinstance(result, (str, bytes)) or not isinstance(result, Sequence):
        raise WebhookExtensionError(f"webhook_contribution_invalid: plugin {plugin!r} returned no sequence from {hook}")
    return result


def _consumers(results: Mapping[str, object]) -> dict[EventType, list[RegisteredConsumer]]:
    by_type: dict[EventType, list[RegisteredConsumer]] = {}
    for plugin, result in results.items():
        for consumer in _contributions(plugin, result, CONSUMERS_HOOK):
            if not isinstance(consumer, EventConsumer):
                raise WebhookExtensionError(
                    f"webhook_consumer_invalid: plugin {plugin!r} contributed a value that is not an EventConsumer"
                )
            event_types = consumer.event_types
            if not isinstance(event_types, frozenset) or not event_types or not event_types <= CONSUMABLE_TYPES:
                raise WebhookExtensionError(
                    f"webhook_consumer_event_types_invalid: plugin {plugin!r} names {sorted(map(str, event_types))}; "
                    f"a consumer names one or more of {sorted(CONSUMABLE_TYPES)}"
                )
            for event_type in sorted(event_types):
                by_type.setdefault(event_type, []).append(RegisteredConsumer(plugin, consumer))
    return by_type


def _handlers(results: Mapping[str, object]) -> dict[str, EventHandler]:
    handlers: dict[str, EventHandler] = {}
    owners: dict[str, str] = {}
    for plugin, result in results.items():
        for handler in _contributions(plugin, result, HANDLERS_HOOK):
            if not isinstance(handler, EventHandler):
                raise WebhookExtensionError(
                    f"webhook_handler_invalid: plugin {plugin!r} contributed a value that is not an EventHandler"
                )
            handler_id = handler.handler_id
            if not isinstance(handler_id, str) or not _HANDLER_ID.fullmatch(handler_id):
                raise WebhookExtensionError(
                    f"webhook_handler_id_invalid: plugin {plugin!r} contributed a handler without a dotted id"
                )
            if handler_id in owners:
                raise WebhookExtensionError(
                    f"webhook_handler_duplicate: {handler_id!r} is registered by plugins {owners[handler_id]!r} and {plugin!r}"
                )
            owners[handler_id] = plugin
            handlers[handler_id] = handler
    return handlers


def _check_kind_handlers(catalogue: ContentCatalogue, handlers: Mapping[str, EventHandler]) -> None:
    unknown = sorted(
        kind_id
        for kind_id, kind in catalogue.items(sender_kinds_content_kind()).items()
        if kind.handler is not None and kind.handler not in handlers
    )
    if unknown:
        raise WebhookExtensionError(f"webhook_kind_handler_unknown: sender kinds {unknown} name a handler no plugin registered")


def poster_for(
    posters: Mapping[WorkplaceSystem, ChannelPoster], destination: Destination, event_type: EventType | None
) -> ChannelPoster | None:
    """The poster for ``destination``'s system, or None when that system has none.

    ``slack.passthrough`` is Slack-shaped JSON, so only a Slack destination receives it.
    """
    if event_type is EventType.SLACK_PASSTHROUGH and destination.system is not WorkplaceSystem.SLACK:
        return None
    return posters.get(destination.system)


def fallback_message(
    translator: Translator, languages: Sequence[str], *, source: str, decoded: JsonDocument, limit: int
) -> FallbackMessage:
    """The fallback rendering: the bot's header in ``languages`` over the decoded message, cut to ``limit``."""
    header = MultilingualText.of(languages, lambda language: translator.translate(FALLBACK_HEADER_KEY, language))
    return FallbackMessage(header=header, source=source, body=fallback_body(decoded, limit))


PASSTHROUGH_PROTOCOL = "legacy_slack_json"


class IngestOutcome(StrEnum):
    """What persisting a delivery came to; the route answers each."""

    PERSISTED = "persisted"
    DUPLICATE = "duplicate"
    UNAVAILABLE = "unavailable"
    TOO_LARGE = "too_large"


@dataclass
class _Run:
    """One attempt's progress over an item it owns."""

    item: InboxItem
    lost: bool = False
    transient: bool = False
    retry_after: float | None = None
    permanent: list[str] = field(default_factory=list)
    render_problem: str | None = None
    kind_id: str | None = None

    def wait_at_least(self, retry_after: float | None) -> None:
        self.transient = True
        if retry_after is not None:
            self.retry_after = max(self.retry_after or 0.0, retry_after)


class WebhookProcessor:
    """Persists deliveries and processes inbox items, inline and from the sweeper."""

    def __init__(
        self,
        *,
        inbox: InboxStore,
        instances: WebhookStore,
        catalogue: ContentCatalogue,
        languages: LanguagePolicy,
        translator: Translator,
        extensions: WebhookExtensions,
        posters: Mapping[WorkplaceSystem, ChannelPoster],
        confirmer: SubscriptionConfirmer,
        settings: WebhooksSettings,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        new_token: Callable[[], str] = lambda: uuid.uuid4().hex,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._inbox = inbox
        self._instances = instances
        self._catalogue = catalogue
        self._languages = languages
        self._translator = translator
        self._extensions = extensions
        self._posters = posters
        self._confirmer = confirmer
        self._settings = settings
        self._clock = clock
        self._new_token = new_token
        self._jitter = jitter

    @property
    def _lease_seconds(self) -> int:
        return math.ceil(self._settings.inline_processing_deadline_seconds) + self._settings.processing_lease_margin_seconds

    async def ingest(self, instance: WebhookInstance, delivery: ProtocolDelivery) -> IngestOutcome:
        """Persist ``delivery`` as an inbox item, then process it inline within the deadline.

        Only a confirmed insert counts: any other store outcome is UNAVAILABLE, and nothing
        is processed (fail closed). The outcome never depends on how processing went.
        """
        envelope = json.dumps(delivery.document, ensure_ascii=False, separators=(",", ":")).encode()
        if len(envelope) > self._settings.max_envelope_bytes:
            return IngestOutcome.TOO_LARGE
        item = new_item(
            instance.instance_ref,
            instance.protocol,
            delivery,
            now=self._clock(),
            owner=self._new_token(),
            lease_seconds=self._lease_seconds,
            ttl_seconds=self._settings.inbox_ttl_seconds,
        )
        inserted = await self._inbox.insert(item)
        if not inserted.is_success:
            return IngestOutcome.UNAVAILABLE
        log = logger.bind(instance_ref=instance.instance_ref, protocol=instance.protocol, item_kind=item.kind.value)
        if inserted.data is not True:
            log.info("webhook_duplicate")
            return IngestOutcome.DUPLICATE
        log.info("webhook_received", fingerprint=list(item.fingerprint))
        await self._attempt(item, instance)
        return IngestOutcome.PERSISTED

    async def sweep(self) -> int:
        """Take due items, under their old owner's token, and process each; return how many were taken."""
        now = self._clock()
        due = await self._inbox.due(now, self._settings.sweeper_batch_size)
        if not due.is_success or due.data is None:
            logger.warning("webhook_sweep_skipped", reason="inbox_unavailable")
            return 0
        taken = 0
        for listed in due.data:
            fresh = await self._inbox.get(listed.key)
            if not fresh.is_success or fresh.data is None or not claimable(fresh.data, now):
                continue
            item = fresh.data
            if item.attempts >= self._settings.retry_max_attempts:
                await self._dead(item, reason="attempts")
                continue
            instance = await self._instances.by_ref(item.instance_ref)
            if instance.status is OperationStatus.NOT_FOUND:
                await self._dead(item, reason="instance_not_found")
                continue
            if not instance.is_success or instance.data is None:
                continue
            if instance.data.state is InstanceState.DISABLED:
                await self._dead(item, reason="instance_disabled")
                continue
            owned = claimed(item, owner=self._new_token(), now=now, lease_seconds=self._lease_seconds)
            result = await self._inbox.replace(item, owned)
            if result.data is None:
                continue
            taken += 1
            await self._attempt(owned, instance.data)
        return taken

    async def _attempt(self, item: InboxItem, instance: WebhookInstance) -> None:
        """Process ``item`` within the deadline; an unfinished attempt keeps its lease for the sweeper."""
        log = logger.bind(instance_ref=item.instance_ref, attempt=item.attempts)
        try:
            async with asyncio.timeout(self._settings.inline_processing_deadline_seconds):
                await self.process(item, instance)
        except TimeoutError:
            log.warning("webhook_processing_deadline")
        except Exception:
            # The boundary of one attempt: the item stays leased and the sweeper retries it.
            log.exception("webhook_processing_failed")

    async def process(self, item: InboxItem, instance: WebhookInstance) -> None:
        """Run ``item``'s work once under its owner token and record the outcome."""
        run = _Run(item)
        match item.kind:
            case ItemKind.SUBSCRIPTION_CONFIRMATION:
                await self._confirm(run)
            case ItemKind.UNSUBSCRIBE_CONFIRMATION:
                logger.info("webhook_sns_unsubscribed", instance_ref=item.instance_ref)
            case ItemKind.EVENT:
                await self._deliver(run, instance)
        await self._settle(run)

    async def _confirm(self, run: _Run) -> None:
        if run.item.subscribe_url is None:
            run.permanent.append("confirm")
            return
        result = await self._confirmer.confirm(run.item.subscribe_url)
        if result.status is OperationStatus.TRANSIENT_ERROR:
            run.wait_at_least(result.retry_after)
        elif not result.is_success:
            run.permanent.append("confirm")
        else:
            logger.info("webhook_sns_subscription_confirmed", instance_ref=run.item.instance_ref)

    def _kinds(self, instance: WebhookInstance) -> tuple[SenderKind, ...]:
        catalogue = self._catalogue.items(sender_kinds_content_kind())
        kinds, skipped = resolve_kinds(instance, catalogue, max_kinds=self._settings.max_kinds_per_instance)
        if skipped:
            logger.warning("webhook_kinds_skipped", instance_ref=instance.instance_ref, kinds=list(skipped))
        return kinds

    def _message(
        self, run: _Run, instance: WebhookInstance, kinds: Sequence[SenderKind], destination: Destination
    ) -> tuple[EventType | None, OutboundMessage] | None:
        """What to post to ``destination``, or None when the matched kind posts nothing."""
        if instance.protocol == PASSTHROUGH_PROTOCOL:
            message = run.item.envelope if isinstance(run.item.envelope, Mapping) else {}
            return EventType.SLACK_PASSTHROUGH, PassthroughMessage(message)
        languages = self._languages.shared_languages(
            system=destination.system, tenant=destination.tenant, conversation_id=destination.conversation_id
        )
        interpretation = interpret(
            kinds, run.item.envelope, self._delivery(run.item, instance), languages=languages, limits=self._settings.limits()
        )
        match interpretation:
            case Matched(kind=kind, event=event):
                actions = self._extensions.actions_for(event, languages) if destination.triage else ()
                return event.type, channel_message(event, actions=actions, mentions=kind.mentions)
            case Suppressed():
                return None
            case Unmatched():
                run.render_problem = "unmatched"
            case RenderFailed(kind_id=kind_id, field=field_name, reason=reason):
                if run.render_problem is None:
                    logger.warning(
                        "webhook_render_failed",
                        instance_ref=instance.instance_ref,
                        kind_id=kind_id,
                        field=field_name,
                        reason=reason,
                    )
                run.render_problem, run.kind_id = "render_failed", kind_id
        fallback = fallback_message(
            self._translator, languages, source=instance.name, decoded=run.item.envelope, limit=self._settings.max_render_chars
        )
        return None, fallback

    @staticmethod
    def _delivery(item: InboxItem, instance: WebhookInstance) -> Delivery:
        return Delivery(
            event_id=item.delivery_id, instance_ref=item.instance_ref, instance_name=instance.name, received_at=item.received_at
        )

    async def _deliver(self, run: _Run, instance: WebhookInstance) -> None:
        kinds = () if instance.protocol == PASSTHROUGH_PROTOCOL else self._kinds(instance)
        sessions: dict[WorkplaceSystem, DeliveryPoster] = {}
        for destination in instance.destinations:
            target = post_target(destination)
            if target in run.item.done_targets:
                continue
            planned = self._message(run, instance, kinds, destination)
            if planned is None:
                continue
            event_type, message = planned
            poster = poster_for(self._posters, destination, event_type)
            if poster is None:
                logger.warning(
                    "webhook_destination_skipped",
                    instance_ref=instance.instance_ref,
                    system=destination.system.value,
                    reason="no_poster",
                )
                continue
            session = sessions.get(destination.system)
            if session is None:
                session = sessions[destination.system] = poster.for_delivery()
            result = await session.post(destination, message)
            if not await self._record(run, target, result):
                return
        if run.render_problem == "unmatched":
            logger.info("webhook_unmatched", instance_ref=instance.instance_ref, protocol=instance.protocol)
        if instance.protocol != PASSTHROUGH_PROTOCOL:
            await self._features(run, instance, kinds)

    async def _record(self, run: _Run, target: str, result: OperationResult[Any]) -> bool:
        """Record a target's result; False when the item was taken over and the attempt must stop."""
        if result.status is OperationStatus.TRANSIENT_ERROR:
            run.wait_at_least(result.retry_after)
            return True
        if not result.is_success:
            logger.warning(
                "webhook_target_failed",
                instance_ref=run.item.instance_ref,
                target=target.split(":", 1)[0],
                error_code=result.error_code,
            )
            run.permanent.append(target)
            return True
        progressed = with_target_done(run.item, target)
        written = await self._inbox.replace(run.item, progressed)
        if written.is_success and written.data is None:
            run.lost = True
            return False
        if written.is_success:
            run.item = progressed
        else:
            logger.warning("webhook_progress_not_recorded", instance_ref=run.item.instance_ref)
        return True

    async def _features(self, run: _Run, instance: WebhookInstance, kinds: Sequence[SenderKind]) -> None:
        """Hand the event to the consumers of its type and to the kind's handler, each once."""
        languages = self._languages.reply_languages(None)
        interpretation = interpret(
            kinds, run.item.envelope, self._delivery(run.item, instance), languages=languages, limits=self._settings.limits()
        )
        if not isinstance(interpretation, Matched):
            return
        event, kind = interpretation.event, interpretation.kind
        context = EventContext(item_id=run.item.key, service_scopes=self._extensions.service_scopes)
        calls: list[tuple[str, Callable[[], Awaitable[None]]]] = [
            (consume_target(registered.plugin), partial(registered.consumer.consume, event, context))
            for registered in self._extensions.consumers_for(event.type)
        ]
        handler = self._extensions.handler(kind.handler) if kind.handler else None
        if handler is not None and kind.handler is not None:
            calls.append((handler_target(kind.handler), partial(handler.handle, event, context)))
        for target, call in calls:
            if target in run.item.done_targets:
                continue
            try:
                await call()
            except Exception:
                logger.exception("webhook_feature_failed", instance_ref=instance.instance_ref, target=target)
                run.wait_at_least(None)
                continue
            if not await self._record(run, target, OperationResult.success()):
                return

    async def _settle(self, run: _Run) -> None:
        if run.lost:
            return
        item = run.item
        if run.transient:
            if item.attempts >= self._settings.retry_max_attempts:
                await self._dead(item, reason="attempts", kind_id=run.kind_id)
                return
            retry_at = next_retry_at(
                self._clock(),
                attempts=item.attempts,
                retry_after=run.retry_after,
                base_seconds=self._settings.retry_base_seconds,
                max_seconds=self._settings.retry_max_seconds,
                random=self._jitter,
            )
            await self._inbox.replace(item, retry_scheduled(item, retry_at=retry_at, error="transient"))
        elif run.permanent:
            await self._dead(item, reason="permanent", kind_id=run.kind_id)
        elif run.render_problem is not None:
            await self._inbox.replace(item, finished(item, ItemState.RENDER_FAILED, error=run.render_problem))
        else:
            await self._inbox.replace(item, finished(item, ItemState.DONE))

    async def _dead(self, item: InboxItem, *, reason: str, kind_id: str | None = None) -> None:
        result = await self._inbox.replace(item, finished(item, ItemState.DEAD, error=reason))
        if result.data is not None:
            logger.warning(
                "webhook_dead_lettered", instance_ref=item.instance_ref, kind_id=kind_id, attempts=item.attempts, reason=reason
            )
