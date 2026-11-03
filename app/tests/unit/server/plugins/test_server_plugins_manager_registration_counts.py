"""Unit tests for the registration phase event the plugin manager logs.

Plugins implementing different hooks are registered on a real pluggy manager that
replaces the application singleton. The phase logs one info event carrying the phase name
and how many plugins implemented each registration hook; the per-hook completion lines and
the manager's construction line are debug.
"""

from types import ModuleType
from unittest.mock import MagicMock

import pluggy
import pytest
import structlog
from structlog.testing import capture_logs

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE, hookimpl
from server.plugins import manager as manager_module

pytestmark = pytest.mark.unit


def _plugin(**hookimpls: object) -> ModuleType:
    plugin = ModuleType("fake_plugin")
    plugin.__dict__.update(hookimpls)
    return plugin


@hookimpl
def register_slack_commands(registrar: object) -> None:
    return None


@hookimpl
def register_routes(app: object) -> None:
    return None


@hookimpl
def startup_warmup(logger: object) -> None:
    return None


def _manager(**plugins: object) -> pluggy.PluginManager:
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)
    for name, plugin in plugins.items():
        pm.register(plugin, name=name)
    return pm


def _register(monkeypatch: pytest.MonkeyPatch, pm: pluggy.PluginManager, *, with_slack: bool = True) -> list[dict[str, object]]:
    monkeypatch.setattr(manager_module, "get_plugin_manager", lambda: pm)
    with capture_logs() as entries:
        manager_module.register_feature_integrations(
            app=MagicMock(),
            logger=structlog.stdlib.get_logger(),
            slack_provider=MagicMock() if with_slack else None,
        )
    return entries


def test_registration_logs_one_info_event_with_the_per_hook_plugin_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """One feature_integrations_registered info event counts the plugins that implemented each hook."""
    pm = _manager(
        commands=_plugin(register_slack_commands=register_slack_commands),
        both=_plugin(register_slack_commands=register_slack_commands, register_routes=register_routes),
        warm=_plugin(startup_warmup=startup_warmup),
        quiet=_plugin(),
    )

    entries = _register(monkeypatch, pm)

    info = [entry for entry in entries if entry["log_level"] == "info"]
    assert [entry["event"] for entry in info] == ["feature_integrations_registered"]
    assert info[0]["phase"] == "feature_registration"
    assert info[0]["slack_command_plugins"] == 2
    assert info[0]["route_plugins"] == 1
    assert info[0]["warmup_plugins"] == 1


def test_registration_counts_zero_slack_plugins_without_a_slack_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no Slack registrar no command hook runs, so the command count is zero."""
    pm = _manager(commands=_plugin(register_slack_commands=register_slack_commands))

    entries = _register(monkeypatch, pm, with_slack=False)

    event = next(entry for entry in entries if entry["event"] == "feature_integrations_registered")
    assert event["slack_command_plugins"] == 0


def test_registration_step_lines_are_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    """The per-hook completion lines are debug, so only the phase event is info."""
    entries = _register(monkeypatch, _manager(warm=_plugin(startup_warmup=startup_warmup)))

    debug = {entry["event"] for entry in entries if entry["log_level"] == "debug"}
    assert {"slack_commands_registered", "feature_routes_registered", "feature_startup_warmup_completed"} <= debug


def test_manager_construction_and_requirement_lines_are_debug() -> None:
    """Creating the manager and resolving requirements log at debug; feature_plugins_loaded keeps its level."""
    manager_module.get_plugin_manager.cache_clear()
    try:
        with capture_logs() as entries:
            manager_module.get_plugin_manager()
    finally:
        manager_module.get_plugin_manager.cache_clear()

    assert [(entry["event"], entry["log_level"]) for entry in entries] == [("plugin_manager_created", "debug")]
