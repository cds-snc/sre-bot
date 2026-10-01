"""Unit tests for event handler hookspec registration."""

from unittest.mock import MagicMock

import pluggy
import pytest

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE, hookimpl
from infrastructure.events.service import EventDispatcher
from server.plugins.manager import register_feature_integrations

pytestmark = pytest.mark.unit


def test_register_event_handlers_hookspec_exists() -> None:
    assert hasattr(FeatureLifecycleSpecs, "register_event_handlers")


def test_hookimpl_receives_dispatcher() -> None:
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)
    observed: dict[str, object] = {}

    class Plugin:
        @hookimpl
        def register_event_handlers(self, dispatcher: EventDispatcher) -> None:
            observed["dispatcher"] = dispatcher

    plugin = Plugin()
    pm.register(plugin)

    dispatcher = EventDispatcher()
    pm.hook.register_event_handlers(dispatcher=dispatcher)

    assert observed["dispatcher"] is dispatcher


def test_hookspec_called_during_feature_integration(monkeypatch) -> None:
    mocked_hook = MagicMock()
    fake_pm = MagicMock()
    fake_pm.hook.register_event_handlers = mocked_hook

    monkeypatch.setattr(
        "server.plugins.manager.get_plugin_manager",
        lambda: fake_pm,
    )

    dispatcher = EventDispatcher()
    register_feature_integrations(
        app=MagicMock(),
        logger=MagicMock(),
        event_dispatcher=dispatcher,
    )

    mocked_hook.assert_called_once_with(dispatcher=dispatcher)
