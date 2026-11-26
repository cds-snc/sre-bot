"""Webhooks application services: the extension point's initialize and its frozen value.

``initialize_extensions`` runs once, in the host's extension-point phase. Every contributed
value comes from another plugin, so each is validated, and a bad one fails boot naming the
plugin. The returned ``WebhookExtensions`` is read at runtime; no pluggy hook is called after
startup (decisions/plugins.md).
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

import structlog

from capabilities.webhooks.domain.events import EventType, InboundEvent, JsonDocument
from capabilities.webhooks.domain.extensions import EventAction, EventConsumer, EventHandler
from capabilities.webhooks.domain.kinds import Destination
from capabilities.webhooks.domain.messages import FallbackMessage, fallback_body
from capabilities.webhooks.interfaces import ChannelPoster
from capabilities.webhooks.schemas import HANDLER_ID_PATTERN, sender_kinds_content_kind
from contracts.content import ContentCatalogue
from contracts.i18n.translator import Translator
from contracts.languages import MultilingualText
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
