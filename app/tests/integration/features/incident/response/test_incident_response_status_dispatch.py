"""Routing ``/sre incident status ...`` through the real Slack provider to the incident.response plugin.

The real ``features.incident.response.plugin`` module is registered on a real
pluggy PluginManager under its entry-point name ``incident.response`` and its
``register_slack_commands`` hook runs against a real ``SlackPlatformProvider``,
whose scope opener resolves an in-memory record store seeded with one legacy
incident on the channel (Slack and Google configured). The response providers
return the core in-memory report, list projection and conversation fakes. Text
is routed with ``route_hierarchical_command`` as the provider routes a slash
command, so the assertions cover the command tree as Slack reaches it: the
reply, the stored status (read back through the real incident store), and what
the report, list and channel fakes received.
"""

import asyncio
from types import SimpleNamespace
from typing import cast

import pluggy
import pytest
from pydantic import SecretStr

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from contracts.slack.models import CommandPayload
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentListProjection,
    InMemoryIncidentReport,
)
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

pytestmark = pytest.mark.integration

CHANNEL_ID = "C0INCIDENT"
USER_ID = "U0INVOKER"
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="D0REPORT")
HELP = (
    "`/sre incident status update <status>` changes this incident's status.\n"
    "*Valid statuses:* In Progress, Open, Ready to be Reviewed, Reviewed, Closed"
)


class _Routed:
    """The provider with the plugin's commands registered, over seeded records and the core fakes."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.records = InMemoryRecordStore()
        seed_legacy_incident(
            self.records, CHANNEL_ID, incident_id="inc-1", report_url="https://docs.google.com/document/d/D0REPORT/edit"
        )
        self.reports = InMemoryIncidentReport(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0")
        self.reports.seed_sections(REPORT, [])
        self.projection = InMemoryIncidentListProjection()
        self.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, open_ids=[CHANNEL_ID])
        monkeypatch.setattr(providers, "incident_report", lambda: self.reports)
        monkeypatch.setattr(providers, "incident_list_projection", lambda: self.projection)
        monkeypatch.setattr(providers, "incident_conversation", lambda: self.conversations)

        settings = SimpleNamespace(app_token=SecretStr("xapp-test"), bot_token=SecretStr("xoxb-test"))
        self.provider = SlackPlatformProvider(settings=cast(SlackSettings, settings), formatter=SlackBlockKitFormatter())
        self.provider.set_scope_opener(incident_scopes(self.records, tenants=TENANTS))
        manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
        manager.add_hookspecs(FeatureLifecycleSpecs)
        manager.register(plugin, name="incident.response")
        manager.hook.register_slack_commands(registrar=self.provider)

    def sre(self, text: str) -> str:
        payload = CommandPayload(text=text, user_id=USER_ID, channel_id=CHANNEL_ID)
        response = self.provider.route_hierarchical_command("sre", text, payload)
        assert response.ephemeral
        return response.message

    def stored_status(self) -> IncidentStatus:
        found = asyncio.run(record_incident_store(self.records, tenants=TENANTS).get("inc-1"))
        assert found.data is not None
        return found.data.status


@pytest.fixture
def routed(monkeypatch: pytest.MonkeyPatch) -> _Routed:
    return _Routed(monkeypatch)


def test_status_update_writes_the_record_and_fans_out(routed: _Routed) -> None:
    """The slash path now writes the record, then the report line, the list cell and the channel notice."""
    reply = routed.sre("incident status update Ready to be Reviewed")

    assert reply == "The incident status is now Ready to be Reviewed."
    assert routed.stored_status() is IncidentStatus.READY_TO_BE_REVIEWED
    assert routed.reports.status_text_of(REPORT) is IncidentStatus.READY_TO_BE_REVIEWED
    assert [row[3] for row in routed.projection.rows] == ["Ready to be Reviewed"]
    assert routed.conversations.posts_in(slack_conversation(CHANNEL_ID)) == (
        f"<@{USER_ID}> has updated the incident status to Ready to be Reviewed.\n"
        f"<@{USER_ID}> a changé le statut de l'incident à Ready to be Reviewed.",
    )


def test_closing_takes_the_incident_off_the_open_list(routed: _Routed) -> None:
    routed.sre("incident status update Closed")

    listed = asyncio.run(record_incident_store(routed.records, tenants=TENANTS).list_open())

    assert routed.stored_status() is IncidentStatus.CLOSED
    assert list(listed.data or ()) == []


def test_a_bare_status_answers_the_pointer_and_writes_nothing(routed: _Routed) -> None:
    reply = routed.sre("incident status Closed")

    assert reply == "Use `/sre incident status update Closed` to change the status."
    assert routed.stored_status() is IncidentStatus.OPEN
    assert routed.conversations.posts_in(slack_conversation(CHANNEL_ID)) == ()


@pytest.mark.parametrize("text", ["incident status", "incident status show"])
def test_status_alone_and_status_show_answer_the_help(routed: _Routed, text: str) -> None:
    assert routed.sre(text) == HELP
    assert routed.stored_status() is IncidentStatus.OPEN
