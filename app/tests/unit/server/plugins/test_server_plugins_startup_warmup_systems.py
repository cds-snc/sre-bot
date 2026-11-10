"""Unit tests for the configured systems the host hands each plugin's startup warmup.

A real pluggy PluginManager holds two module-like plugins and replaces the cached
manager for ``register_feature_integrations``. One warmup asks for the configured
systems and records what it receives; the other takes only the logger, the shape
every warmup had before the argument existed, and must still run.
"""

from collections.abc import Iterator
from types import ModuleType
from unittest.mock import MagicMock

import pluggy
import pytest

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE, hookimpl
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from server.plugins.manager import register_feature_integrations
from tests.factories.incident import FakeConfiguredSystems

pytestmark = pytest.mark.unit


@pytest.fixture
def pm(monkeypatch: pytest.MonkeyPatch) -> Iterator[pluggy.PluginManager]:
    manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
    manager.add_hookspecs(FeatureLifecycleSpecs)
    monkeypatch.setattr("server.plugins.manager.get_plugin_manager", lambda: manager)
    yield manager


def test_warmups_receive_the_configured_systems_and_logger_only_warmups_still_run(pm: pluggy.PluginManager) -> None:
    received: list[ConfiguredSystems] = []
    calls: list[str] = []

    @hookimpl
    def reads_systems(logger: object, systems: ConfiguredSystems) -> None:
        received.append(systems)

    @hookimpl
    def logger_only(logger: object) -> None:
        calls.append("logger_only")

    first = ModuleType("first")
    first.__dict__["startup_warmup"] = reads_systems
    second = ModuleType("second")
    second.__dict__["startup_warmup"] = logger_only
    pm.register(first, name="demo.first")
    pm.register(second, name="demo.second")
    systems = FakeConfiguredSystems({WorkplaceSystem.SLACK: "T0123"})

    register_feature_integrations(app=MagicMock(), logger=MagicMock(), systems=systems)

    assert received == [systems]
    assert calls == ["logger_only"]
