"""Pinning tests for the legacy incident declare surface.

Covers ``/incident``, the ``incident_change_locale`` button, the ``incident_view``
submission and the ``handle_incident_action_buttons`` alert buttons. Each test
dispatches a Slack request through ``slack_bolt.App.dispatch`` on the legacy
handler harness and asserts only what Slack and the external edges observe:
the HTTP ack, the Web API calls recorded on the fake Slack client, the Sentinel
events, the webhook acknowledged-count increments, and the payload handed to
the incident resource fan-out.

The fan-out (Drive folder, report document, Sheets row, Meet, record write) is
replaced by one recorder on ``core.initiate_resources_creation``, the name the
submission resolves at call time; its resource-by-resource behaviour is not
part of the Slack surface.
"""

import json
from datetime import datetime
from typing import Any

import pytest
from slack_sdk.errors import SlackApiError

from models.incidents import IncidentPayload
from modules.incident import core as incident_core
from modules.incident import incident_conversation

from .conftest import TRIGGER_ID, USER_ID, LegacyHandlerHarness

pytestmark = pytest.mark.integration

ALERT_CHANNEL_ID = "C0ALERTS"
ALERT_MESSAGE_TS = "1700000000.000100"
SUBMIT_TRIGGER_ID = "trigger-submit"
NEW_CHANNEL_ID = "C0NEWINCIDENT"
EXPECTED_PRODUCT_OPTIONS = [
    {"text": {"type": "plain_text", "text": "Forms"}, "value": "F0FORMS"},
    {"text": {"type": "plain_text", "text": "Platform"}, "value": "F0PLATFORM"},
]
IGNORED_MESSAGE = (
    f"🙈  <@{USER_ID}> has acknowledged and ignored the incident.\n<@{USER_ID}> a pris connaissance et ignoré l'incident."
)


@pytest.fixture
def fan_out(monkeypatch: pytest.MonkeyPatch) -> list[IncidentPayload]:
    """Record each payload handed to the incident resource fan-out instead of creating resources."""
    payloads: list[IncidentPayload] = []

    def record(client: Any, incident_payload: IncidentPayload) -> None:
        payloads.append(incident_payload)

    monkeypatch.setattr(incident_core, "initiate_resources_creation", record)
    return payloads


def _block(view: dict[str, Any], block_id: str) -> dict[str, Any]:
    return next(block for block in view["blocks"] if block.get("block_id") == block_id)


def _locale_button(view: dict[str, Any]) -> dict[str, Any]:
    element: dict[str, Any] = _block(view, "locale")["elements"][0]
    return element


def _sentinel_event_names(harness: LegacyHandlerHarness) -> list[str]:
    return [event["event"] for event in harness.sentinel_events]


def _declare_submission(name: str, *, private_metadata: str = "", locale: str = "en-US") -> dict[str, Any]:
    return {
        "type": "view_submission",
        "trigger_id": SUBMIT_TRIGGER_ID,
        "view": {
            "id": "V0DECLARE",
            "type": "modal",
            "callback_id": "incident_view",
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


def _expected_slug(name: str) -> str:
    return f"{datetime.now().strftime('%Y-%m-%d')}-{name.replace(' ', '-').lower()}"


def _expected_channel_name(name: str) -> str:
    """Environment prefix plus slug, cut to Slack's 80-character channel name limit."""
    prefix = "incident-dev-" if incident_conversation.settings.ENVIRONMENT != "production" else "incident-"
    return f"{prefix}{_expected_slug(name)}"[:80]


# /incident


def test_incident_command_opens_a_loading_modal_then_the_declare_form(legacy_handler_harness: LegacyHandlerHarness) -> None:
    """The command acks empty, opens a loading view on its trigger, then fills it with the declare form.

    The product options come from the faked Drive folder listing in name order,
    and the command text pre-fills the description field.
    """
    response = legacy_handler_harness.command("incident", "database outage")

    assert (response.status, response.body) == (200, "")
    assert legacy_handler_harness.responses == []
    client = legacy_handler_harness.client
    assert client.calls_to("users_info") == [{"user": USER_ID, "include_locale": True}]
    [opened] = client.calls_to("views_open")
    assert opened["trigger_id"] == TRIGGER_ID
    assert opened["view"]["callback_id"] == "incident_view"
    assert opened["view"]["title"]["text"] == "SRE - Start an incident"
    assert "Launching incident process..." in opened["view"]["blocks"][0]["text"]["text"]
    [updated] = client.calls_to("views_update")
    assert updated["view_id"] == "VFAKE"
    form = updated["view"]
    assert form["callback_id"] == "incident_view"
    assert form["title"]["text"] == "SRE - Start an incident"
    assert form["private_metadata"] == ""
    assert _locale_button(form)["action_id"] == "incident_change_locale"
    assert (_locale_button(form)["value"], _locale_button(form)["text"]["text"]) == ("en-US", "Français")
    assert _block(form, "name")["element"]["initial_value"] == "database outage"
    assert _block(form, "product")["element"]["options"] == EXPECTED_PRODUCT_OPTIONS
    assert [option["value"] for option in _block(form, "severity")["element"]["options"]] == [
        "none",
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
    legacy_handler_harness: LegacyHandlerHarness, user_locale: str, expected_locale: str, expected_title: str
) -> None:
    """A French Slack locale renders the French form; an unsupported one falls back to English."""
    legacy_handler_harness.client.replies["users_info"] = {"ok": True, "user": {"id": USER_ID, "locale": user_locale}}

    legacy_handler_harness.command("incident")

    [updated] = legacy_handler_harness.client.calls_to("views_update")
    assert updated["view"]["title"]["text"] == expected_title
    assert _locale_button(updated["view"])["value"] == expected_locale
    assert _block(updated["view"], "name")["element"]["initial_value"] == ""


# incident_change_locale


@pytest.mark.parametrize(
    ("current_locale", "expected_locale", "expected_title", "expected_button_text"),
    [
        ("en-US", "fr-FR", "IFS - Lancer un incident", "English"),
        ("fr-FR", "en-US", "SRE - Start an incident", "Français"),
    ],
)
def test_locale_button_rerenders_the_open_form_in_the_other_language(
    legacy_handler_harness: LegacyHandlerHarness,
    current_locale: str,
    expected_locale: str,
    expected_title: str,
    expected_button_text: str,
) -> None:
    """The button acks, then updates the same view in the other locale, keeping the typed name and metadata."""
    response = legacy_handler_harness.interaction(
        {
            "type": "block_actions",
            "trigger_id": "trigger-locale",
            "actions": [{"type": "button", "block_id": "locale", "action_id": "incident_change_locale", "value": current_locale}],
            "view": {
                "id": "V0DECLARE",
                "type": "modal",
                "callback_id": "incident_view",
                "private_metadata": "alert-metadata",
                "state": {"values": {"name": {"name": {"type": "plain_text_input", "value": "database outage"}}}},
            },
        }
    )

    assert response.status == 200
    [updated] = legacy_handler_harness.client.calls_to("views_update")
    assert updated["view_id"] == "V0DECLARE"
    form = updated["view"]
    assert form["title"]["text"] == expected_title
    assert (_locale_button(form)["value"], _locale_button(form)["text"]["text"]) == (expected_locale, expected_button_text)
    assert _block(form, "name")["element"]["initial_value"] == "database outage"
    assert _block(form, "product")["element"]["options"] == EXPECTED_PRODUCT_OPTIONS
    assert form["private_metadata"] == "alert-metadata"


def test_locale_button_keeps_an_empty_name_empty(legacy_handler_harness: LegacyHandlerHarness) -> None:
    """A form with no description typed yet re-renders with an empty description, not ``None``."""
    legacy_handler_harness.interaction(
        {
            "type": "block_actions",
            "actions": [{"type": "button", "block_id": "locale", "action_id": "incident_change_locale", "value": "en-US"}],
            "view": {"id": "V0DECLARE", "type": "modal", "state": {"values": {"name": {"name": {"value": None}}}}},
        }
    )

    [updated] = legacy_handler_harness.client.calls_to("views_update")
    assert _block(updated["view"], "name")["element"]["initial_value"] == ""


# incident_view


@pytest.mark.parametrize("name", ["database outage", "a" * 59])
def test_declare_submission_creates_the_channel_and_hands_the_incident_to_the_fan_out(
    legacy_handler_harness: LegacyHandlerHarness, fan_out: list[IncidentPayload], name: str
) -> None:
    """A valid submission acks empty, creates the dated channel, shows the success modal and fans out once.

    The 59-character name is the longest the form accepts; its channel name is
    cut to 80 characters while the slug keeps the whole name.
    """
    response = legacy_handler_harness.interaction(_declare_submission(name))

    assert (response.status, response.body) == (200, "")
    client = legacy_handler_harness.client
    channel_name = _expected_channel_name(name)
    assert client.calls_to("conversations_create") == [{"name": channel_name}]
    [success] = client.calls_to("views_open")
    assert success["trigger_id"] == SUBMIT_TRIGGER_ID
    assert success["view"]["blocks"][0]["text"]["text"] == "Incident successfully created"
    assert f"<#{NEW_CHANNEL_ID}|{channel_name}>" in success["view"]["blocks"][1]["text"]["text"]
    assert _sentinel_event_names(legacy_handler_harness) == ["incident_called"]
    assert fan_out == [
        IncidentPayload(
            name=name,
            folder="F0FORMS",
            product="Forms",
            security_incident="no",
            user_id=USER_ID,
            channel_id=NEW_CHANNEL_ID,
            channel_name=channel_name,
            slug=_expected_slug(name),
            severity="sev-2",
            source_alert_permalink=None,
        )
    ]
    assert client.calls_to("chat_postMessage") == []


def test_declare_submission_shows_the_success_modal_in_the_forms_locale(
    legacy_handler_harness: LegacyHandlerHarness, fan_out: list[IncidentPayload]
) -> None:
    """The success modal follows the locale of the submitted form's language button."""
    legacy_handler_harness.interaction(_declare_submission("database outage", locale="fr-FR"))

    [success] = legacy_handler_harness.client.calls_to("views_open")
    assert success["view"]["blocks"][0]["text"]["text"] == "Incident créé avec succès"


def test_declare_submission_from_an_alert_links_the_source_message(
    legacy_handler_harness: LegacyHandlerHarness, fan_out: list[IncidentPayload]
) -> None:
    """Alert metadata in the view resolves to the alert's permalink, which travels with the incident."""
    legacy_handler_harness.client.replies["chat_getPermalink"] = {"ok": True, "permalink": "https://slack.test/archives/alert"}
    metadata = json.dumps({"source_channel_id": ALERT_CHANNEL_ID, "source_message_ts": ALERT_MESSAGE_TS})

    legacy_handler_harness.interaction(_declare_submission("database outage", private_metadata=metadata))

    assert legacy_handler_harness.client.calls_to("chat_getPermalink") == [
        {"channel": ALERT_CHANNEL_ID, "message_ts": ALERT_MESSAGE_TS}
    ]
    [payload] = fan_out
    assert payload.source_alert_permalink == "https://slack.test/archives/alert"


def test_declare_submission_continues_without_a_link_when_the_permalink_lookup_fails(
    legacy_handler_harness: LegacyHandlerHarness, fan_out: list[IncidentPayload]
) -> None:
    """A failed permalink lookup does not block the declaration; the incident carries no source link."""
    legacy_handler_harness.client.replies["chat_getPermalink"] = SlackApiError("message_not_found", {"ok": False})
    metadata = json.dumps({"source_channel_id": ALERT_CHANNEL_ID, "source_message_ts": ALERT_MESSAGE_TS})

    legacy_handler_harness.interaction(_declare_submission("database outage", private_metadata=metadata))

    [payload] = fan_out
    assert payload.source_alert_permalink is None
    assert legacy_handler_harness.client.calls_to("conversations_create") != []


def test_declare_submission_warns_the_invoker_when_the_channel_cannot_be_created(
    legacy_handler_harness: LegacyHandlerHarness, fan_out: list[IncidentPayload]
) -> None:
    """A Slack refusal to create the channel sends the invoker a warning and stops before any other step."""
    legacy_handler_harness.client.replies["conversations_create"] = {"ok": False, "error": "restricted_action"}

    response = legacy_handler_harness.interaction(_declare_submission("database outage"))

    assert response.status == 200
    client = legacy_handler_harness.client
    assert [(call["channel"], call["text"]) for call in client.calls_to("chat_postMessage")] == [
        (USER_ID, ":warning: Channel creation failed. Please contact the SRE team.")
    ]
    assert client.calls_to("views_open") == []
    assert legacy_handler_harness.sentinel_events == []
    assert fan_out == []


def test_declare_submission_warns_the_new_channel_when_the_fan_out_fails(
    legacy_handler_harness: LegacyHandlerHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fan-out failure after the channel exists posts the warning into that channel."""

    def fail(client: Any, incident_payload: IncidentPayload) -> None:
        raise RuntimeError("drive unavailable")

    monkeypatch.setattr(incident_core, "initiate_resources_creation", fail)

    response = legacy_handler_harness.interaction(_declare_submission("database outage"))

    assert response.status == 200
    assert [(call["channel"], call["text"]) for call in legacy_handler_harness.client.calls_to("chat_postMessage")] == [
        (NEW_CHANNEL_ID, ":warning: There was an error initiating the incident resources. Please contact the SRE team.")
    ]


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
    legacy_handler_harness: LegacyHandlerHarness, fan_out: list[IncidentPayload], name: str, expected_error: str
) -> None:
    """An invalid description answers with a bilingual field error and creates no channel.

    The handler acks once before validating and again with the errors. Bolt
    answers with the last ack set by the time it reads the response; the
    harness runs the listener to completion first, so the errors ack is the
    one observed.
    """
    response = legacy_handler_harness.interaction(_declare_submission(name))

    assert response.status == 200
    assert json.loads(response.body) == {"response_action": "errors", "errors": {"name": expected_error}}
    assert legacy_handler_harness.client.calls_to("conversations_create") == []
    assert legacy_handler_harness.client.calls_to("views_open") == []
    assert fan_out == []


# handle_incident_action_buttons


def test_call_incident_button_opens_the_declare_form_prefilled_from_the_alert(
    legacy_handler_harness: LegacyHandlerHarness,
) -> None:
    """The call-incident button opens the declare form named after the alert and carrying the alert's location."""
    response = legacy_handler_harness.interaction(_alert_button_press("call-incident", "Disk full on prod"))

    assert (response.status, response.body) == (200, "")
    client = legacy_handler_harness.client
    [opened] = client.calls_to("views_open")
    assert opened["trigger_id"] == "trigger-alert"
    [updated] = client.calls_to("views_update")
    form = updated["view"]
    assert _block(form, "name")["element"]["initial_value"] == "Disk full on prod"
    assert json.loads(form["private_metadata"]) == {
        "source_channel_id": ALERT_CHANNEL_ID,
        "source_message_ts": ALERT_MESSAGE_TS,
    }
    assert _sentinel_event_names(legacy_handler_harness) == ["call_incident_button_pressed"]


def test_ignore_incident_button_acknowledges_the_webhook_and_replaces_the_buttons(
    legacy_handler_harness: LegacyHandlerHarness,
) -> None:
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

    response = legacy_handler_harness.interaction(_alert_button_press("ignore-incident", "hook-123", original_message))

    assert (response.status, response.body) == (200, "")
    assert legacy_handler_harness.acknowledged_webhooks == ["hook-123"]
    [update] = legacy_handler_harness.client.calls_to("chat_update")
    assert update["channel"] == ALERT_CHANNEL_ID
    assert update["ts"] == ALERT_MESSAGE_TS
    assert update["attachments"] == [
        {"color": "danger", "text": "Disk full on prod"},
        {"color": "3AA3E3", "fallback": IGNORED_MESSAGE, "text": IGNORED_MESSAGE},
    ]
    assert update["blocks"] == []
    assert _sentinel_event_names(legacy_handler_harness) == ["ignore_incident_button_pressed"]


def test_ignore_incident_button_keeps_blocks_that_are_not_rich_text(legacy_handler_harness: LegacyHandlerHarness) -> None:
    """Only rich_text blocks are cleared; an alert with section blocks keeps them in the update."""
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Disk full on prod"}}]
    original_message = {"text": "", "blocks": blocks, "attachments": [{"callback_id": "handle_incident_action_buttons"}]}

    legacy_handler_harness.interaction(_alert_button_press("ignore-incident", "hook-123", original_message))

    [update] = legacy_handler_harness.client.calls_to("chat_update")
    assert update["blocks"] == blocks
    assert update["attachments"] == [{"color": "3AA3E3", "fallback": IGNORED_MESSAGE, "text": IGNORED_MESSAGE}]
