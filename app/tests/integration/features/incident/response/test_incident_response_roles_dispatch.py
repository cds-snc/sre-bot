"""Routing ``/sre incident roles ...`` to the incident.response plugin, and the modal flow it registers.

The real ``features.incident.response.plugin`` module is registered on a real pluggy PluginManager
under its entry-point name ``incident.response``. Text is routed through a real ``SlackPlatformProvider``
with ``route_hierarchical_command``, as the provider routes a slash command, so the assertions cover the
command tree as Slack reaches it. The modal flow runs the plugin's registrations on a recording registrar:
the ``roles manage`` handler opens the modal on its reply, and the view submission listener it registered
is called with that modal's own ids. The scope opener resolves an in-memory record store seeded with one
legacy incident on the channel; the response providers return the core in-memory conversation and legacy
roles reader. Assertions read the stored roles, the channel's posts and purpose and the help text.
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
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.adapters.in_memory import InMemoryIncidentConversation, InMemoryLegacyRolesReader
from features.incident.core.api import ReportReference
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
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="D0REPORT")


class _Routed:
    """The plugin registered on a real provider and on a recording registrar, over seeded records and the core fakes."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.records = InMemoryRecordStore()
        seed_legacy_incident(
            self.records, CHANNEL_ID, incident_id="inc-1", report_url="https://docs.google.com/document/d/D0REPORT/edit"
        )
        self.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, open_ids=[CHANNEL_ID])
        self.conversations.seed_purpose(slack_conversation(CHANNEL_ID), "Checkout outage")
        legacy = InMemoryLegacyRolesReader()
        legacy.seed(REPORT, {IncidentRole.INCIDENT_COMMANDER: "U0OLDIC", IncidentRole.OPERATIONS_LEAD: "U0OLDOL"})
        monkeypatch.setattr(providers, "incident_conversation", lambda: self.conversations)
        monkeypatch.setattr(providers, "legacy_roles_reader", lambda: legacy)

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

    def open_modal(self) -> dict[str, Any]:
        """Run the registered ``roles manage`` handler and return the view it opened."""
        [manage] = [command for command in self.registrar.commands if command["command"] == "manage"]
        payload = CommandPayload(
            text="",
            user_id=USER_ID,
            channel_id=CHANNEL_ID,
            platform_metadata={"trigger_id": "T0TRIGGER", "channel_name": "incident-2026-10-checkout"},
        )
        manage["handler"](payload)
        [opened] = self.registrar.reply.calls_to("open_view")  # type: ignore[attr-defined]
        view: dict[str, Any] = opened["view"]
        return view

    def submit(self, view: dict[str, Any], picks: dict[str, str]) -> None:
        """Submit ``view`` with the users in ``picks`` (by block id) over what it preselected."""
        values: dict[str, Any] = {}
        for block in view["blocks"]:
            if block["type"] == "input":
                chosen = picks.get(block["block_id"], block["element"].get("initial_user"))
                values[block["block_id"]] = {block["element"]["action_id"]: {"selected_user": chosen}}
        body = {
            "user": {"id": USER_ID},
            "view": {"private_metadata": view["private_metadata"], "state": {"values": values}},
        }
        listener = self.registrar.view_submissions[view["callback_id"]]
        listener(ack=lambda **_: None, body=body, client=SimpleNamespace(chat_postEphemeral=lambda **_: {"ok": True}))

    def stored(self) -> dict[str, str | None]:
        found = asyncio.run(record_incident_store(self.records, tenants=TENANTS).get("inc-1"))
        assert found.data is not None
        return {role.value: getattr(found.data, role.value) for role in IncidentRole}


@pytest.fixture
def routed(monkeypatch: pytest.MonkeyPatch) -> _Routed:
    return _Routed(monkeypatch)


@pytest.mark.parametrize("text", ["incident roles", "incident roles show"])
def test_roles_alone_and_roles_show_answer_the_roles_help(routed: _Routed, text: str) -> None:
    reply = routed.sre(text)

    assert "manage" in reply
    assert routed.stored()["incident_commander"] is None


def test_roles_manage_is_routed_to_its_handler(routed: _Routed) -> None:
    """Without a trigger id the handler answers that the window could not open, which only it can say."""
    assert routed.sre("incident roles manage") == "Couldn't open the roles window. Please try again."


def test_the_modal_opens_on_the_legacy_report_roles_and_its_submission_writes_the_record(routed: _Routed) -> None:
    view = routed.open_modal()

    routed.submit(view, {"incident.response.roles.operations_lead": "U0NEWOL", "incident.response.roles.policy_lead": "U0POLICY"})

    assert routed.stored() == {
        "incident_commander": "U0OLDIC",
        "operations_lead": "U0NEWOL",
        "communications_lead": None,
        "policy_lead": "U0POLICY",
        "postmortem_owner": None,
    }
    assert routed.conversations.posts_in(slack_conversation(CHANNEL_ID)) == (
        "<@U0NEWOL> has been assigned as operations lead for this incident.\n"
        "<@U0NEWOL> a été désigné(e) responsable des opérations pour cet incident.",
        "<@U0POLICY> has been assigned as policy lead for this incident.\n"
        "<@U0POLICY> a été désigné(e) responsable des politiques pour cet incident.",
    )
    assert routed.conversations.purpose_of(slack_conversation(CHANNEL_ID)) == "Checkout outage \nIC: <@U0OLDIC> / OL: <@U0NEWOL>"
