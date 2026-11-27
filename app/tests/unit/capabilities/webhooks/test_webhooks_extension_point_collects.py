"""Unit tests for the webhooks extension point: consumers by event type, handlers by id.

Stub strategy: the real webhooks plugin module and test feature modules are registered on a
real pluggy manager with the host hookspecs, and the host's extension-point phase runs
against a real svcs registry holding an in-memory content catalogue. The assertions cover
what a plugin author observes: the frozen value in the registry, and a boot failure that
names the plugin or the sender kind at fault.
"""

from collections.abc import Iterator, Sequence
from types import ModuleType
from typing import Any

import pluggy
import pytest
import structlog
import svcs

import capabilities.webhooks.plugin as webhooks_plugin
from capabilities.webhooks.api import EventAction, EventConsumer, EventContext, EventHandler, EventType, InboundEvent
from capabilities.webhooks.schemas import sender_kinds_content_kind
from capabilities.webhooks.service import WebhookExtensionError, WebhookExtensions
from contracts.content import ContentCatalogue
from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE, hookimpl
from infrastructure.content.in_memory import InMemoryContentCatalogue
from server.plugins.extension_points import run_extension_points
from server.services import SvcsServiceScopeOpener
from tests.unit.capabilities.webhooks.conftest import build_kind, kind_document

pytestmark = pytest.mark.unit


class _Consumer:
    def __init__(self, *event_types: EventType) -> None:
        self.event_types = frozenset(event_types)
        self.events: list[InboundEvent] = []

    def actions(self, event: InboundEvent, languages: Sequence[str]) -> tuple[EventAction, ...]:
        return ()

    async def consume(self, event: InboundEvent, context: EventContext) -> None:
        self.events.append(event)


class _Handler:
    def __init__(self, handler_id: str) -> None:
        self.handler_id = handler_id

    async def handle(self, event: InboundEvent, context: EventContext) -> None:
        return None


def _feature(name: str, *, consumers: Sequence[object] = (), handlers: Sequence[object] = ()) -> ModuleType:
    calls: list[str] = []

    @hookimpl
    def register_webhook_consumers() -> list[object]:
        calls.append("consumers")
        return list(consumers)

    @hookimpl
    def register_webhook_handlers() -> list[object]:
        calls.append("handlers")
        return list(handlers)

    plugin = ModuleType(f"features.{name}.plugin")
    plugin.__dict__.update(
        register_webhook_consumers=register_webhook_consumers,
        register_webhook_handlers=register_webhook_handlers,
        calls=calls,
    )
    return plugin


@pytest.fixture
def registry() -> Iterator[svcs.Registry]:
    with svcs.Registry() as registry:
        registry.register_value(ContentCatalogue, InMemoryContentCatalogue())
        yield registry


def _boot(registry: svcs.Registry, **features: ModuleType) -> WebhookExtensions:
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)
    pm.register(webhooks_plugin, name="webhooks")
    for name, feature in features.items():
        pm.register(feature, name=name)
    run_extension_points(pm, registry, SvcsServiceScopeOpener(registry), structlog.stdlib.get_logger())
    with svcs.Container(registry) as container:
        return container.get(WebhookExtensions)


def test_an_empty_point_is_valid() -> None:
    """The capability's own poster serves when no feature contributes."""
    with svcs.Registry() as registry:
        registry.register_value(ContentCatalogue, InMemoryContentCatalogue())
        extensions = _boot(registry)

    assert extensions.consumers_for(EventType.ALERT) == ()
    assert extensions.handler("notify.revoke_key") is None


def test_consumers_are_collected_by_event_type_in_load_order(registry: svcs.Registry) -> None:
    """Each consumer is listed under every type it names, with the plugin that contributed it."""
    first, second = _Consumer(EventType.ALERT), _Consumer(EventType.ALERT, EventType.NOTIFICATION)

    extensions = _boot(registry, incident=_feature("incident", consumers=[first]), audit=_feature("audit", consumers=[second]))

    assert [(c.plugin, c.consumer) for c in extensions.consumers_for(EventType.ALERT)] == [("incident", first), ("audit", second)]
    assert [c.consumer for c in extensions.consumers_for(EventType.NOTIFICATION)] == [second]


def test_handlers_are_collected_by_id(registry: svcs.Registry) -> None:
    handler = _Handler("notify.revoke_key")

    extensions = _boot(registry, notify=_feature("notify", handlers=[handler]))

    assert extensions.handler("notify.revoke_key") is handler


def test_the_value_is_frozen(registry: svcs.Registry) -> None:
    """Nothing adds a consumer after startup."""
    extensions = _boot(registry, incident=_feature("incident", consumers=[_Consumer(EventType.ALERT)]))

    with pytest.raises(TypeError):
        extensions.consumers[EventType.ALERT] = ()  # type: ignore[index]


def test_a_duplicate_handler_id_fails_boot_naming_both_plugins(registry: svcs.Registry) -> None:
    with pytest.raises(WebhookExtensionError, match=r"notify.*other|other.*notify"):
        _boot(
            registry,
            notify=_feature("notify", handlers=[_Handler("notify.revoke_key")]),
            other=_feature("other", handlers=[_Handler("notify.revoke_key")]),
        )


@pytest.mark.parametrize("event_types", [(), ("page",), (EventType.SLACK_PASSTHROUGH,)])
def test_a_consumer_for_no_or_an_unknown_or_the_opaque_type_fails_boot_naming_the_plugin(
    registry: svcs.Registry, event_types: tuple[Any, ...]
) -> None:
    """slack.passthrough is opaque Slack JSON: there is nothing typed for a consumer to read."""
    consumer = _Consumer()
    consumer.event_types = frozenset(event_types)

    with pytest.raises(WebhookExtensionError, match="rogue"):
        _boot(registry, rogue=_feature("rogue", consumers=[consumer]))


@pytest.mark.parametrize("bad", ["not a consumer", 42])
def test_a_value_that_is_not_a_consumer_fails_boot_naming_the_plugin(registry: svcs.Registry, bad: object) -> None:
    with pytest.raises(WebhookExtensionError, match="rogue"):
        _boot(registry, rogue=_feature("rogue", consumers=[bad]))


def test_a_result_that_is_not_a_sequence_fails_boot_naming_the_plugin(registry: svcs.Registry) -> None:
    @hookimpl
    def register_webhook_handlers() -> object:
        return _Handler("rogue.one")

    plugin = ModuleType("features.rogue.plugin")
    plugin.__dict__.update(register_webhook_handlers=register_webhook_handlers)

    with pytest.raises(WebhookExtensionError, match="rogue"):
        _boot(registry, rogue=plugin)


def test_a_handler_id_outside_the_dotted_form_fails_boot_naming_the_plugin(registry: svcs.Registry) -> None:
    with pytest.raises(WebhookExtensionError, match="rogue"):
        _boot(registry, rogue=_feature("rogue", handlers=[_Handler("Revoke Key")]))


def test_a_sender_kind_naming_an_unregistered_handler_fails_boot_naming_the_kind() -> None:
    """The content's handler: names are checked against what plugins registered."""
    catalogue = InMemoryContentCatalogue()
    catalogue.add(
        sender_kinds_content_kind(), "notify-key", build_kind(kind_document(id="notify-key", handler="notify.revoke_key"))
    )
    with svcs.Registry() as registry:
        registry.register_value(ContentCatalogue, catalogue)

        with pytest.raises(WebhookExtensionError, match="notify-key"):
            _boot(registry)


def test_no_hook_is_called_after_startup(registry: svcs.Registry) -> None:
    """Reading the value never calls back into pluggy."""
    feature = _feature("incident", consumers=[_Consumer(EventType.ALERT)])
    extensions = _boot(registry, incident=feature)
    calls_at_boot = list(feature.calls)

    extensions.consumers_for(EventType.ALERT)
    extensions.handler("x.y")

    assert feature.calls == calls_at_boot == ["consumers", "handlers"]


def test_the_contracts_are_runtime_checkable() -> None:
    """The phase validates contributions structurally, so a plugin needs no base class."""
    assert isinstance(_Consumer(EventType.ALERT), EventConsumer)
    assert isinstance(_Handler("a.b"), EventHandler)
