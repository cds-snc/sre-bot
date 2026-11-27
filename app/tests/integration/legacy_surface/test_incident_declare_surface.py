"""Pinning tests for the incident declare surface.

Covers ``/incident``, the form's locale button, its submission and the
``handle_incident_action_buttons`` alert buttons. Each test dispatches a Slack
request through ``slack_bolt.App.dispatch``, and the provider routes it to the
rebuilt ``incident.response`` plugin (the declare cutover). Assertions are on what
Slack and the external edges observe: the HTTP ack, the Web API calls recorded on
the fake Slack client, the Sentinel events, and the incident as the declare wrote it,
read back from the core in-memory fakes in domain terms.

The fixture is rewired to the target's fakes (decisions/migration.md step 4): the
plugin's scope opener resolves an in-memory record store (incidents, bindings and
the webhooks table) and claims store, and the response providers return the core
in-memory report (its placements are the products), list projection, conversation,
video call, placement schedule lookup and the on-call capability's in-memory lookup.
The legacy fan-out recorder is gone: the declare is record first, so the incident is
asserted on the store. Edited assertions cite the declare cutover's named changes:
N1 (record first: a failed channel leaves a recorded incident and its Sentinel
event), N4 (SEV0 in the severity options), N9 (the incident channel's warning in the
instance languages), N16 (the form's callback and locale ids are the plugin's; the
command answers with an empty ephemeral reply, as every host command does; the
success view names the channel by id, which Slack renders as its name). The new
behaviour is tested under tests/unit/features/incident/response/.
"""

import asyncio
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pytest
from slack_sdk.errors import SlackApiError

from capabilities.oncall.adapters.in_memory import InMemoryOnCallLookup
from contracts.operations import OperationResult
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import Severity
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentListProjection,
    InMemoryIncidentReport,
    InMemoryPlacementScheduleLookup,
    InMemoryVideoCall,
)
from features.incident.core.api import Incident, ReportPlacement, ReportReference
from features.incident.response import plugin, providers
from features.incident.response.adapters.alert_acknowledgements import WEBHOOKS_TABLE
from features.incident.response.entrypoints.slack_declare_views import DECLARE_CALLBACK_ID, LOCALE_ACTION_ID
from features.incident.response.service.declare import incident_id_for
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.i18n import load_plugin_catalogues, reset_translation_service
from tests.factories.incident import GOOGLE_TENANT, SLACK_TENANT, incident_scopes, record_incident_store

from .conftest import TRIGGER_ID, USER_ID, IncidentSurface

pytestmark = pytest.mark.integration

ALERT_CHANNEL_ID = "C0ALERTS"
ALERT_MESSAGE_TS = "1700000000.000100"
SUBMIT_TRIGGER_ID = "trigger-submit"
VIEW_ID = "V0DECLARE"
NEW_CHANNEL_ID = "C0NEW1"
PLACEMENTS = (("F0PLATFORM", "Platform"), ("F0FORMS", "Forms"))
EXPECTED_PRODUCT_OPTIONS = [
    {"text": {"type": "plain_text", "text": "Forms"}, "value": "F0FORMS"},
    {"text": {"type": "plain_text", "text": "Platform"}, "value": "F0PLATFORM"},
]
IGNORED_MESSAGE = (
    f"🙈  <@{USER_ID}> has acknowledged and ignored the incident.\n<@{USER_ID}> a pris connaissance et ignoré l'incident."
)
# N9: the incident channel is a shared conversation, written in English and French.
RESOURCES_WARNING = (
    ":warning: There was an error initiating the incident resources. Please contact the SRE team.\n"
    ":warning: Une erreur est survenue lors de la création des ressources de l'incident. "
    "Veuillez communiquer avec l'équipe SRE."
)


class RefusingConversation(InMemoryIncidentConversation):
    """Slack refuses every channel creation."""

    async def create(self, name: Any, *, private: bool) -> OperationResult[Any]:
        return OperationResult.permanent_error("restricted_action", error_code="restricted_action")


class FailingReport(InMemoryIncidentReport):
    """Drive refuses to create the report; the placements still list."""

    async def create_from_template(
        self, title: str, placement: ReportPlacement | None = None
    ) -> OperationResult[ReportReference]:
        return OperationResult.transient_error("drive unavailable")


@dataclass
class DeclareSurface:
    """The declare surface over the core fakes, each kept for assertions."""

    surface: IncidentSurface
    records: InMemoryRecordStore
    conversations: InMemoryIncidentConversation
    reports: InMemoryIncidentReport

    @property
    def client(self) -> Any:
        return self.surface.slack.client

    def command(self, text: str = "") -> Any:
        return self.surface.slack.command("incident", text)

    def interaction(self, payload: dict[str, Any]) -> Any:
        return self.surface.slack.interaction(payload)

    def sentinel_event_names(self) -> list[str]:
        return [event["event"] for event in self.surface.slack.sentinel_events]

    def incident(self) -> Incident | None:
        """The incident the form's view declared, as stored."""
        store = record_incident_store(self.records, tenants=TENANTS)
        return asyncio.run(store.get(incident_id_for(f"slack:{SLACK_TENANT}:{VIEW_ID}"))).data

    def acknowledged_count(self, webhook_id: str) -> int:
        item = self.records.get(WEBHOOKS_TABLE, {"id": webhook_id}).data or {}
        return int(item.get("acknowledged_count", 0))


TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}


def _surface(
    incident_surface: IncidentSurface,
    monkeypatch: pytest.MonkeyPatch,
    *,
    conversations: InMemoryIncidentConversation | None = None,
    reports: InMemoryIncidentReport | None = None,
) -> DeclareSurface:
    records = InMemoryRecordStore()
    records.put(WEBHOOKS_TABLE, {"id": "hook-123", "name": "alerts"})
    reports = reports if reports is not None else InMemoryIncidentReport(next_ids=["D0REPORT"], placements=PLACEMENTS)
    conversations = conversations if conversations is not None else InMemoryIncidentConversation(tenant=SLACK_TENANT)
    monkeypatch.setattr(providers, "incident_report", lambda: reports)
    monkeypatch.setattr(providers, "incident_list_projection", InMemoryIncidentListProjection)
    monkeypatch.setattr(providers, "incident_conversation", lambda: conversations)
    monkeypatch.setattr(providers, "video_call", InMemoryVideoCall)
    monkeypatch.setattr(providers, "placement_schedule_lookup", InMemoryPlacementScheduleLookup)
    monkeypatch.setattr(providers, "oncall_lookup", lambda: InMemoryOnCallLookup(people={}))

    incident_surface.provider.set_scope_opener(incident_scopes(records, tenants=TENANTS))
    plugin.register_slack_commands(registrar=incident_surface.provider)
    # The Bolt app is built before the plugin registers: wire its listeners and its /incident root command.
    incident_surface.provider._attach_interaction_listeners()
    incident_surface.provider._auto_register_root_commands()
    load_plugin_catalogues(plugin.register_i18n_resources)
    return DeclareSurface(incident_surface, records, conversations, reports)


@pytest.fixture
def declare_surface(incident_surface: IncidentSurface, monkeypatch: pytest.MonkeyPatch) -> Iterator[DeclareSurface]:
    """The declare surface with the response plugin registered over the core in-memory fakes."""
    yield _surface(incident_surface, monkeypatch)
    reset_translation_service()


def _block(view: dict[str, Any], block_id: str) -> dict[str, Any]:
    return next(block for block in view["blocks"] if block.get("block_id") == block_id)


def _locale_button(view: dict[str, Any]) -> dict[str, Any]:
    element: dict[str, Any] = _block(view, "locale")["elements"][0]
    return element


def _declare_submission(name: str, *, private_metadata: str = "", locale: str = "en-US") -> dict[str, Any]:
    return {
        "type": "view_submission",
        "trigger_id": SUBMIT_TRIGGER_ID,
        "view": {
            "id": VIEW_ID,
            "type": "modal",
            "callback_id": DECLARE_CALLBACK_ID,
            "private_metadata": private_metadata,
            "blocks": [{"type": "actions", "block_id": "locale", "elements": [{"type": "button", "value": locale}]}],
            "state": {
                "values": {
                    "name": {"name": {"type": "plain_text_input", "value": name}},
                    "product": {
                        "product": {
                            "type": "static_select",
                            "selected_option": {"text": {"type": "plain_text", "text": "Forms"}, "value": "F0FORMS"},
                        }
                    },
                    "security_incident": {"security_incident": {"type": "static_select", "selected_option": {"value": "no"}}},
                    "severity": {"severity": {"type": "static_select", "selected_option": {"value": "sev-2"}}},
                }
            },
        },
    }


def _alert_button_press(name: str, value: str, original_message: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "interactive_message",
        "callback_id": "handle_incident_action_buttons",
        "actions": [{"name": name, "type": "button", "value": value}],
        "channel": {"id": ALERT_CHANNEL_ID},
        "message_ts": ALERT_MESSAGE_TS,
        "trigger_id": "trigger-alert",
        "original_message": original_message or {"text": "", "attachments": []},
    }


def _expected_channel_name(name: str) -> str:
    """Instance prefix plus slug, cut to Slack's 80-character channel name limit.

    The prefix follows ``[incident_core] dev_conversation_names`` (local.toml says true), which
    replaces the legacy environment-name check.
    """
    prefix = "incident-dev-" if get_incident_core_settings().dev_conversation_names else "incident-"
    slug = f"{datetime.now().strftime('%Y-%m-%d')}-{name.replace(' ', '-').lower()}"
    return f"{prefix}{slug}"[:80]


# /incident


def test_incident_command_opens_a_loading_modal_then_the_declare_form(declare_surface: DeclareSurface) -> None:
    """The command acks empty, opens a loading view on its trigger, then fills it with the declare form.

    The product options are the report placements in name order, and the command
    text pre-fills the description field. N4: the severity options offer SEV0. N16:
    the form's ids are the plugin's, and the command answers one empty ephemeral reply.
    """
    response = declare_surface.command("database outage")

    assert (response.status, response.body) == (200, "")
    assert [message["text"] for message in declare_surface.surface.slack.responses] == [""]
    client = declare_surface.client
    assert client.calls_to("users_info") == [{"user": USER_ID, "include_locale": True}]
    [opened] = client.calls_to("views_open")
    assert opened["trigger_id"] == TRIGGER_ID
    assert opened["view"]["callback_id"] == DECLARE_CALLBACK_ID
    assert opened["view"]["title"]["text"] == "SRE - Start an incident"
    assert "Launching incident process..." in opened["view"]["blocks"][0]["text"]["text"]
    [updated] = client.calls_to("views_update")
    assert updated["view_id"] == "VFAKE"
    form = updated["view"]
    assert form["callback_id"] == DECLARE_CALLBACK_ID
    assert form["title"]["text"] == "SRE - Start an incident"
    assert form["private_metadata"] == ""
    assert _locale_button(form)["action_id"] == LOCALE_ACTION_ID
    assert (_locale_button(form)["value"], _locale_button(form)["text"]["text"]) == ("en-US", "Français")
    assert _block(form, "name")["element"]["initial_value"] == "database outage"
    assert _block(form, "product")["element"]["options"] == EXPECTED_PRODUCT_OPTIONS
    assert [option["value"] for option in _block(form, "severity")["element"]["options"]] == [
        "none",
        "sev-0",
        "sev-1",
        "sev-2",
        "sev-3",
        "sev-4",
    ]


@pytest.mark.parametrize(
    ("user_locale", "expected_locale", "expected_title"),
    [
        ("fr-FR", "fr-FR", "IFS - Lancer un incident"),
        ("de-DE", "en-US", "SRE - Start an incident"),
    ],
)
def test_incident_command_renders_the_form_in_the_invokers_supported_locale(
    declare_surface: DeclareSurface, user_locale: str, expected_locale: str, expected_title: str
) -> None:
    """A French Slack locale renders the French form; an unsupported one falls back to English."""
    declare_surface.client.replies["users_info"] = {"ok": True, "user": {"id": USER_ID, "locale": user_locale}}

    declare_surface.command()

    [updated] = declare_surface.client.calls_to("views_update")
    assert updated["view"]["title"]["text"] == expected_title
    assert _locale_button(updated["view"])["value"] == expected_locale
    assert _block(updated["view"], "name")["element"]["initial_value"] == ""


# The locale button


@pytest.mark.parametrize(
    ("current_locale", "expected_locale", "expected_title", "expected_button_text"),
    [
        ("en-US", "fr-FR", "IFS - Lancer un incident", "English"),
        ("fr-FR", "en-US", "SRE - Start an incident", "Français"),
    ],
)
def test_locale_button_rerenders_the_open_form_in_the_other_language(
    declare_surface: DeclareSurface,
    current_locale: str,
    expected_locale: str,
    expected_title: str,
    expected_button_text: str,
) -> None:
    """The button acks, then updates the same view in the other locale, keeping the typed name and metadata."""
    response = declare_surface.interaction(
        {
            "type": "block_actions",
            "trigger_id": "trigger-locale",
            "actions": [{"type": "button", "block_id": "locale", "action_id": LOCALE_ACTION_ID, "value": current_locale}],
            "view": {
                "id": VIEW_ID,
                "type": "modal",
                "callback_id": DECLARE_CALLBACK_ID,
                "private_metadata": "alert-metadata",
                "state": {"values": {"name": {"name": {"type": "plain_text_input", "value": "database outage"}}}},
            },
        }
    )

    assert response.status == 200
    [updated] = declare_surface.client.calls_to("views_update")
    assert updated["view_id"] == VIEW_ID
    form = updated["view"]
    assert form["title"]["text"] == expected_title
    assert (_locale_button(form)["value"], _locale_button(form)["text"]["text"]) == (expected_locale, expected_button_text)
    assert _block(form, "name")["element"]["initial_value"] == "database outage"
    assert _block(form, "product")["element"]["options"] == EXPECTED_PRODUCT_OPTIONS
    assert form["private_metadata"] == "alert-metadata"


def test_locale_button_keeps_an_empty_name_empty(declare_surface: DeclareSurface) -> None:
    """A form with no description typed yet re-renders with an empty description, not ``None``."""
    declare_surface.interaction(
        {
            "type": "block_actions",
            "actions": [{"type": "button", "block_id": "locale", "action_id": LOCALE_ACTION_ID, "value": "en-US"}],
            "view": {"id": VIEW_ID, "type": "modal", "state": {"values": {"name": {"name": {"value": None}}}}},
        }
    )

    [updated] = declare_surface.client.calls_to("views_update")
    assert _block(updated["view"], "name")["element"]["initial_value"] == ""


# The form's submission


@pytest.mark.parametrize("name", ["database outage", "a" * 59])
def test_declare_submission_creates_the_channel_and_hands_the_incident_to_the_fan_out(
    declare_surface: DeclareSurface, name: str
) -> None:
    """A valid submission acks empty, creates the dated channel, shows the success modal and records the incident once.

    The 59-character name is the longest the form accepts; its channel name is
    cut to 80 characters. The incident is recorded with the form's answers and its
    report filed in the chosen product's placement. N16: the success view names the
    channel by id.
    """
    response = declare_surface.interaction(_declare_submission(name))

    assert (response.status, response.body) == (200, "")
    client = declare_surface.client
    assert declare_surface.conversations.created_names == [_expected_channel_name(name)]
    [success] = client.calls_to("views_open")
    assert success["trigger_id"] == SUBMIT_TRIGGER_ID
    assert success["view"]["blocks"][0]["text"]["text"] == "Incident successfully created"
    assert f"<#{NEW_CHANNEL_ID}>" in success["view"]["blocks"][1]["text"]["text"]
    assert declare_surface.sentinel_event_names() == ["incident_called"]
    incident = declare_surface.incident()
    assert incident is not None
    assert (incident.title, incident.declared_by, incident.security_incident, incident.severity) == (
        name,
        USER_ID,
        False,
        Severity.SEV2,
    )
    assert incident.source_alert is None
    assert incident.report is not None and declare_surface.reports.filed_in(incident.report) == "F0FORMS"
    assert client.calls_to("chat_postMessage") == []


def test_declare_submission_shows_the_success_modal_in_the_forms_locale(declare_surface: DeclareSurface) -> None:
    """The success modal follows the locale of the submitted form's language button."""
    declare_surface.interaction(_declare_submission("database outage", locale="fr-FR"))

    [success] = declare_surface.client.calls_to("views_open")
    assert success["view"]["blocks"][0]["text"]["text"] == "Incident créé avec succès"


def test_declare_submission_from_an_alert_links_the_source_message(declare_surface: DeclareSurface) -> None:
    """Alert metadata in the view resolves to the alert's permalink, which travels with the incident."""
    declare_surface.client.replies["chat_getPermalink"] = {"ok": True, "permalink": "https://slack.test/archives/alert"}
    metadata = json.dumps({"source_channel_id": ALERT_CHANNEL_ID, "source_message_ts": ALERT_MESSAGE_TS})

    declare_surface.interaction(_declare_submission("database outage", private_metadata=metadata))

    assert declare_surface.client.calls_to("chat_getPermalink") == [{"channel": ALERT_CHANNEL_ID, "message_ts": ALERT_MESSAGE_TS}]
    incident = declare_surface.incident()
    assert incident is not None and incident.source_alert is not None
    assert incident.source_alert.url == "https://slack.test/archives/alert"


def test_declare_submission_continues_without_a_link_when_the_permalink_lookup_fails(
    declare_surface: DeclareSurface,
) -> None:
    """A failed permalink lookup does not block the declaration; the incident carries no source link."""
    declare_surface.client.replies["chat_getPermalink"] = SlackApiError("message_not_found", {"ok": False})
    metadata = json.dumps({"source_channel_id": ALERT_CHANNEL_ID, "source_message_ts": ALERT_MESSAGE_TS})

    declare_surface.interaction(_declare_submission("database outage", private_metadata=metadata))

    incident = declare_surface.incident()
    assert incident is not None and incident.source_alert is not None
    assert incident.source_alert.url is None
    assert declare_surface.conversations.created_names != []


def test_declare_submission_warns_the_invoker_when_the_channel_cannot_be_created(
    incident_surface: IncidentSurface, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Slack refusal to create the channel sends the invoker a warning and opens no success view.

    N1: the record is written first, so the incident exists without a channel and
    its Sentinel event is sent.
    """
    surface = _surface(incident_surface, monkeypatch, conversations=RefusingConversation(tenant=SLACK_TENANT))
    try:
        response = surface.interaction(_declare_submission("database outage"))
    finally:
        reset_translation_service()

    assert response.status == 200
    client = surface.client
    assert [(call["channel"], call["text"]) for call in client.calls_to("chat_postMessage")] == [
        (USER_ID, ":warning: Channel creation failed. Please contact the SRE team.")
    ]
    assert client.calls_to("views_open") == []
    assert surface.sentinel_event_names() == ["incident_called"]
    incident = surface.incident()
    assert incident is not None and incident.conversation is None


def test_declare_submission_warns_the_new_channel_when_the_fan_out_fails(
    incident_surface: IncidentSurface, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed step after the channel exists posts the warning into that channel (N9: in English and French)."""
    surface = _surface(incident_surface, monkeypatch, reports=FailingReport(placements=PLACEMENTS))
    try:
        response = surface.interaction(_declare_submission("database outage"))
    finally:
        reset_translation_service()

    assert response.status == 200
    incident = surface.incident()
    assert incident is not None and incident.conversation is not None
    assert surface.conversations.posts_in(incident.conversation)[-1] == RESOURCES_WARNING


@pytest.mark.parametrize(
    ("name", "expected_error"),
    [
        (
            "database/outage",
            "Description must only contain number and letters // La description ne doit contenir que des nombres et des lettres",
        ),
        ("a" * 60, "Description must be less than 60 characters // La description doit contenir moins de 60 caractères"),
    ],
)
def test_declare_submission_rejects_an_invalid_name_without_creating_anything(
    declare_surface: DeclareSurface, name: str, expected_error: str
) -> None:
    """An invalid description answers with a bilingual field error and declares nothing; the submission acks once."""
    response = declare_surface.interaction(_declare_submission(name))

    assert response.status == 200
    assert json.loads(response.body) == {"response_action": "errors", "errors": {"name": expected_error}}
    assert declare_surface.conversations.created_names == []
    assert declare_surface.client.calls_to("views_open") == []
    assert declare_surface.incident() is None


# handle_incident_action_buttons


def test_call_incident_button_opens_the_declare_form_prefilled_from_the_alert(declare_surface: DeclareSurface) -> None:
    """The call-incident button opens the declare form named after the alert and carrying the alert's location."""
    response = declare_surface.interaction(_alert_button_press("call-incident", "Disk full on prod"))

    assert (response.status, response.body) == (200, "")
    client = declare_surface.client
    [opened] = client.calls_to("views_open")
    assert opened["trigger_id"] == "trigger-alert"
    [updated] = client.calls_to("views_update")
    form = updated["view"]
    assert _block(form, "name")["element"]["initial_value"] == "Disk full on prod"
    assert json.loads(form["private_metadata"]) == {
        "source_channel_id": ALERT_CHANNEL_ID,
        "source_message_ts": ALERT_MESSAGE_TS,
    }
    assert declare_surface.sentinel_event_names() == ["call_incident_button_pressed"]


def test_ignore_incident_button_acknowledges_the_webhook_and_replaces_the_buttons(declare_surface: DeclareSurface) -> None:
    """The ignore button counts an acknowledgement and rewrites the alert without its buttons.

    Read-only attachment keys Slack echoes back are dropped, the bilingual
    acknowledgement is appended, and rich_text blocks are cleared because
    chat.update rejects them from a bot.
    """
    original_message = {
        "type": "message",
        "ts": ALERT_MESSAGE_TS,
        "text": "",
        "blocks": [{"type": "rich_text", "elements": []}],
        "attachments": [
            {"id": 1, "from_url": "https://slack.test/x", "color": "danger", "text": "Disk full on prod"},
            {"id": 2, "callback_id": "handle_incident_action_buttons", "actions": [{"name": "call-incident"}]},
        ],
    }

    response = declare_surface.interaction(_alert_button_press("ignore-incident", "hook-123", original_message))

    assert (response.status, response.body) == (200, "")
    assert declare_surface.acknowledged_count("hook-123") == 1
    [update] = declare_surface.client.calls_to("chat_update")
    assert update["channel"] == ALERT_CHANNEL_ID
    assert update["ts"] == ALERT_MESSAGE_TS
    assert update["attachments"] == [
        {"color": "danger", "text": "Disk full on prod"},
        {"color": "3AA3E3", "fallback": IGNORED_MESSAGE, "text": IGNORED_MESSAGE},
    ]
    assert update["blocks"] == []
    assert declare_surface.sentinel_event_names() == ["ignore_incident_button_pressed"]


def test_ignore_incident_button_keeps_blocks_that_are_not_rich_text(declare_surface: DeclareSurface) -> None:
    """Only rich_text blocks are cleared; an alert with section blocks keeps them in the update."""
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Disk full on prod"}}]
    original_message = {"text": "", "blocks": blocks, "attachments": [{"callback_id": "handle_incident_action_buttons"}]}

    declare_surface.interaction(_alert_button_press("ignore-incident", "hook-123", original_message))

    [update] = declare_surface.client.calls_to("chat_update")
    assert update["blocks"] == blocks
    assert update["attachments"] == [{"color": "3AA3E3", "fallback": IGNORED_MESSAGE, "text": IGNORED_MESSAGE}]
