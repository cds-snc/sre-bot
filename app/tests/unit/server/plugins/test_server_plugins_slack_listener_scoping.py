"""Unit tests for per-plugin Slack registration in the plugin manager.

A real pluggy PluginManager holds small plugin classes registered under
dotted entry-point names, and replaces the cached manager for
``register_feature_integrations``. The Slack registrar is either a recording
fake (to observe what each plugin registered and under which name) or the real
provider (to prove a registration error aborts the startup call).
"""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pluggy
import pytest

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE, hookimpl
from contracts.slack.registrar import SlackCommandRegistrar
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from server.plugins.manager import register_feature_integrations
from server.plugins.slack_registrar import PluginSlackRegistrar
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit


def listener(**_: Any) -> None:
    """Stand-in Bolt listener."""


class ActionPlugin:
    """Registers one block action and one view submission under the given ids."""

    def __init__(self, action_id: str, callback_id: str) -> None:
        self.action_id = action_id
        self.callback_id = callback_id
        self.received: list[SlackCommandRegistrar] = []

    @hookimpl
    def register_slack_commands(self, registrar: SlackCommandRegistrar) -> None:
        self.received.append(registrar)
        registrar.register_block_action(self.action_id, listener)
        registrar.register_view_submission(self.callback_id, listener)


class CommandPlugin:
    """Registers one command and reads the reply interface."""

    def __init__(self) -> None:
        self.reply: object = None

    @hookimpl
    def register_slack_commands(self, registrar: SlackCommandRegistrar) -> None:
        self.reply = registrar.reply
        registrar.register_command("ping", None, description="Ping", parent="sre")


@pytest.fixture
def pm(monkeypatch: pytest.MonkeyPatch) -> Iterator[pluggy.PluginManager]:
    manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
    manager.add_hookspecs(FeatureLifecycleSpecs)
    monkeypatch.setattr("server.plugins.manager.get_plugin_manager", lambda: manager)
    yield manager


def run_registration(registrar: SlackCommandRegistrar) -> None:
    register_feature_integrations(app=MagicMock(), logger=MagicMock(), slack_provider=registrar)


def real_provider() -> SlackPlatformProvider:
    settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
    return SlackPlatformProvider(settings=settings, formatter=SlackBlockKitFormatter())


def test_each_plugin_receives_a_registrar_scoped_to_its_entry_point_name(pm: pluggy.PluginManager) -> None:
    scribe = ActionPlugin("incident.scribe.approve", "incident.scribe.submit")
    sync = ActionPlugin("access.sync.retry", "access.sync.confirm")
    pm.register(scribe, name="incident.scribe")
    pm.register(sync, name="access.sync")
    registrar = FakeSlackRegistrar()

    run_registration(registrar)

    (scribe_registrar,) = scribe.received
    (sync_registrar,) = sync.received
    assert isinstance(scribe_registrar, PluginSlackRegistrar)
    assert scribe_registrar.plugin_name == "incident.scribe"
    assert isinstance(sync_registrar, PluginSlackRegistrar)
    assert sync_registrar.plugin_name == "access.sync"
    assert set(registrar.block_actions) == {"incident.scribe.approve", "access.sync.retry"}
    assert set(registrar.view_submissions) == {"incident.scribe.submit", "access.sync.confirm"}


@pytest.mark.parametrize(
    ("action_id", "callback_id"),
    [
        ("approve", "incident.scribe.submit"),
        ("incident.scribe.approve", "submit"),
        ("access.sync.approve", "incident.scribe.submit"),
        ("incident.scribe", "incident.scribe.submit"),
        ("incident.scribe2.approve", "incident.scribe.submit"),
    ],
)
def test_id_without_the_plugins_own_prefix_aborts_registration(
    pm: pluggy.PluginManager, action_id: str, callback_id: str
) -> None:
    pm.register(ActionPlugin(action_id, callback_id), name="incident.scribe")

    with pytest.raises(ValueError, match="incident.scribe"):
        run_registration(FakeSlackRegistrar())


def test_duplicate_id_aborts_registration_through_the_real_provider(pm: pluggy.PluginManager) -> None:
    class Duplicate:
        @hookimpl
        def register_slack_commands(self, registrar: SlackCommandRegistrar) -> None:
            registrar.register_block_action("incident.scribe.approve", listener)
            registrar.register_block_action("incident.scribe.approve", listener)

    pm.register(Duplicate(), name="incident.scribe")

    with pytest.raises(ValueError, match="incident.scribe.approve"):
        run_registration(real_provider())


def test_commands_and_reply_pass_through_unchanged(pm: pluggy.PluginManager) -> None:
    plugin = CommandPlugin()
    pm.register(plugin, name="user_rotations")
    registrar = FakeSlackRegistrar()

    run_registration(registrar)

    assert registrar.command("ping", parent="sre")["description"] == "Ping"
    assert plugin.reply is registrar.reply


def test_blocked_plugin_is_not_called(pm: pluggy.PluginManager) -> None:
    pm.set_blocked("incident.scribe")
    sync = ActionPlugin("access.sync.retry", "access.sync.confirm")
    pm.register(sync, name="access.sync")
    registrar = FakeSlackRegistrar()

    run_registration(registrar)

    assert set(registrar.block_actions) == {"access.sync.retry"}


def test_hookimpl_error_propagates(pm: pluggy.PluginManager) -> None:
    class Broken:
        @hookimpl
        def register_slack_commands(self, registrar: SlackCommandRegistrar) -> None:
            raise LookupError("broken plugin")

    pm.register(Broken(), name="rant")

    with pytest.raises(LookupError, match="broken plugin"):
        run_registration(FakeSlackRegistrar())
