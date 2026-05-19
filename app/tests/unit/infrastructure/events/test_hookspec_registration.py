"""Unit tests for event handler hookspec registration."""

from unittest.mock import MagicMock

import pluggy
import pytest

from infrastructure.hookspecs import features
from infrastructure.events.service import EventDispatcher
from infrastructure.plugins.manager import register_feature_integrations

pytestmark = pytest.mark.unit


def test_register_event_handlers_hookspec_exists() -> None:
    assert hasattr(features, "register_event_handlers")


def test_hookimpl_receives_dispatcher() -> None:
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(features)
    observed: dict[str, object] = {}
    hookimpl = pluggy.HookimplMarker("sre_bot")

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
        "infrastructure.plugins.manager.get_plugin_manager",
        lambda: fake_pm,
    )

    dispatcher = EventDispatcher()
    register_feature_integrations(
        app=MagicMock(),
        logger=MagicMock(),
        event_dispatcher=dispatcher,
    )

    mocked_hook.assert_called_once_with(dispatcher=dispatcher)
