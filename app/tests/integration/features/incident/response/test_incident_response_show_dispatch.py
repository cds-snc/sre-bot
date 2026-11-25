"""Routing ``/sre incident show`` to the incident.response plugin, and the update modal flow it registers.

The real ``features.incident.response.plugin`` module is registered on a real pluggy PluginManager under
its entry-point name ``incident.response``. Text is routed through a real ``SlackPlatformProvider`` with
``route_hierarchical_command``, as the provider routes a slash command, so the assertions cover the
command tree as Slack reaches it. The modal flow runs the plugin's registrations on a recording
registrar: the ``show`` handler opens the information modal on its reply, the Update button's listener
pushes the field modal, and the view submission listener is called with that modal's own ids. The scope
opener resolves an in-memory record store seeded with one legacy incident on the channel; the response
providers return the core in-memory conversation, video call and legacy roles reader. Assertions read the
stored record, the channel's posts and the refreshed view.
"""

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import pluggy
import pytest
from pydantic import SecretStr

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from contracts.slack.models import CommandPayload
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import Severity
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryLegacyRolesReader,
    InMemoryVideoCall,
)
from features.incident.core.api import Incident
from features.incident.response import plugin, providers
from infrastructure.records.in_memory import InMemoryRecordStore
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from integrations.slack.settings import SlackSettings
from tests.factories.incident import (
    GOOGLE_TENANT,
    SLACK_TENANT,
    incident_scopes,
    record_incident_store,
    seed_legacy_incident,
    slack_conversation,
)
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.integration

CHANNEL_ID = "C0INCIDENT"
USER_ID = "U0INVOKER"
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}


class _Routed:
    """The plugin registered on a real provider and on a recording registrar, over seeded records and the core fakes."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.records = InMemoryRecordStore()
        seed_legacy_incident(self.records, CHANNEL_ID, incident_id="inc-1", severity="sev-2")
        self.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, open_ids=[CHANNEL_ID])
        monkeypatch.setattr(providers, "incident_conversation", lambda: self.conversations)
        monkeypatch.setattr(providers, "legacy_roles_reader", InMemoryLegacyRolesReader)
        monkeypatch.setattr(providers, "video_call", InMemoryVideoCall)

        scopes = incident_scopes(self.records, tenants=TENANTS)
        settings = SimpleNamespace(app_token=SecretStr("xapp-test"), bot_token=SecretStr("xoxb-test"))
        self.provider = SlackPlatformProvider(settings=cast(SlackSettings, settings), formatter=SlackBlockKitFormatter())
        self.provider.set_scope_opener(scopes)
        self.registrar = FakeSlackRegistrar(service_scopes=scopes)
        manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
        manager.add_hookspecs(FeatureLifecycleSpecs)
        manager.register(plugin, name="incident.response")
        manager.hook.register_slack_commands(registrar=self.provider)
        manager.hook.register_slack_commands(registrar=self.registrar)

    def sre(self, text: str) -> str:
        payload = CommandPayload(text=text, user_id=USER_ID, channel_id=CHANNEL_ID)
        response = self.provider.route_hierarchical_command("sre", text, payload)
        assert response.ephemeral
        return response.message

    def open_info(self) -> dict[str, Any]:
        """Run the registered ``show`` handler and return the view it opened."""
        [show] = [command for command in self.registrar.commands if command["command"] == "show"]
        payload = CommandPayload(text="", user_id=USER_ID, channel_id=CHANNEL_ID, platform_metadata={"trigger_id": "T0TRIGGER"})
        show["handler"](payload)
        view: dict[str, Any] = self.registrar.reply.calls_to("open_view")[-1]["view"]  # type: ignore[attr-defined]
        return view

    def press(self, info: dict[str, Any], field: str) -> dict[str, Any]:
        """Press the Update button of ``field`` through its registered listener and return the pushed view."""
        [button] = [block["accessory"] for block in info["blocks"] if block.get("accessory", {}).get("value") == field]
        body = {
            "trigger_id": "T0CLICK",
            "user": {"id": USER_ID},
            "actions": [{"action_id": button["action_id"], "value": field}],
            "view": {"id": "V0INFO", "root_view_id": "V0ROOT", "private_metadata": info["private_metadata"]},
        }
        self.registrar.block_actions[button["action_id"]](ack=lambda **_: None, body=body)
        view: dict[str, Any] = self.registrar.reply.calls_to("push_view")[-1]["view"]  # type: ignore[attr-defined]
        return view

    def submit(self, view: dict[str, Any], option: str) -> None:
        """Submit the pushed field view with ``option`` selected, through its registered listener."""
        [field_input] = [block for block in view["blocks"] if block["type"] == "input"]
        action_id = field_input["element"]["action_id"]
        body = {
            "user": {"id": USER_ID},
            "view": {
                "id": "V0FIELD",
                "root_view_id": "V0ROOT",
                "private_metadata": view["private_metadata"],
                "state": {"values": {field_input["block_id"]: {action_id: {"selected_option": {"value": option}}}}},
            },
        }
        self.registrar.view_submissions[view["callback_id"]](ack=lambda **_: None, body=body)

    def stored(self) -> Incident:
        found = asyncio.run(record_incident_store(self.records, tenants=TENANTS).get("inc-1"))
        assert found.data is not None
        return found.data


@pytest.fixture
def routed(monkeypatch: pytest.MonkeyPatch) -> _Routed:
    return _Routed(monkeypatch)


@pytest.mark.parametrize("text", ["incident show", "incident show extra words"])
def test_show_is_routed_to_its_handler(routed: _Routed, text: str) -> None:
    """Without a trigger id the handler answers that the window could not open, which only it can say."""
    assert routed.sre(text) == "Couldn't open the incident information window. Please try again."


def test_the_information_modal_updates_a_field_through_its_own_ids_and_refreshes(routed: _Routed) -> None:
    info = routed.open_info()

    routed.submit(routed.press(info, "severity"), "sev-4")

    assert routed.stored().severity is Severity.SEV4
    assert routed.conversations.posts_in(slack_conversation(CHANNEL_ID)) == (
        f"<@{USER_ID}> has updated the field severity to sev-4\n<@{USER_ID}> a mis à jour le champ severity à sev-4",
    )
    [refreshed] = routed.registrar.reply.calls_to("update_view")  # type: ignore[attr-defined]
    assert refreshed["view_id"] == "V0ROOT"
    assert "*Severity*:\nsev-4" in "\n".join(block.get("text", {}).get("text", "") for block in refreshed["view"]["blocks"])


def test_flipping_the_security_flag_through_the_modal_writes_the_record(routed: _Routed) -> None:
    routed.submit(routed.press(routed.open_info(), "security_incident"), "yes")

    assert routed.stored().security_incident is True
