"""``/incident``, the declare form's submission and locale toggle, and their registration.

The handlers run over a scope opener resolving an in-memory record store and claims
store (Slack and Google configured, English then French shared), and the response
providers return the core in-memory report (two placements), list projection,
conversation, video call and placement schedule lookup, with the on-call capability's
in-memory lookup and a recording event sink. Views and replies are read from the fake
reply's recorded calls; ``ack`` is a recorder, so a test can count its calls. Assertions
read what users see (the views, the field errors, the direct messages) and the incident
as stored.

Rules under test (the declare cutover's named changes): the submission is validated before
its single ack; the view id is the idempotency key, so a redelivered submission is one
incident; the record is written first and the declarer is its commander; SEV0 is a
severity (value 0, never read as unset); a failed record write tells the declarer and
creates nothing else; the locale toggle and the legacy ids reach the same handlers.
"""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest

from capabilities.oncall.adapters.in_memory import InMemoryOnCallLookup
from contracts.operations import OperationResult
from contracts.slack.models import CommandPayload
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import Severity
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentListProjection,
    InMemoryIncidentReport,
    InMemoryPlacementScheduleLookup,
    InMemoryVideoCall,
)
from features.incident.core.api import Incident, ReportPlacement
from features.incident.response import providers
from features.incident.response.entrypoints.slack_declare import (
    ALERT_BUTTONS_CALLBACK_ID,
    LEGACY_ALERT_BUTTONS_CALLBACK_ID,
    LEGACY_LOCALE_ACTION_ID,
    handle_declare_command,
    handle_declare_submission,
    handle_locale_toggle,
    register_declare,
)
from features.incident.response.entrypoints.slack_declare_views import DECLARE_CALLBACK_ID, LOCALE_ACTION_ID
from features.incident.response.service.declare import incident_id_for
from features.incident.response.settings import get_incident_response_settings
from tests.factories.incident import GOOGLE_TENANT, SLACK_TENANT, SwitchableRecordStore, incident_scopes, record_incident_store
from tests.factories.slack import FakeSlackRegistrar, FakeSlackReply

pytestmark = pytest.mark.unit

USER = "U0DECLARER"
VIEW_ID = "V0VIEW"
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}
PLACEMENTS = (("F0PAYMENTS", "Payments"), ("F0FORMS", "Forms"))


@dataclass
class Ack:
    """Records each ack call's keyword arguments."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, str]]] = []

    async def send(self, event: str, message: Any) -> None:
        self.events.append((event, dict(message)))


@dataclass
class World:
    records: SwitchableRecordStore
    reports: InMemoryIncidentReport
    conversations: InMemoryIncidentConversation
    sink: RecordingSink
    reply: FakeSlackReply

    @property
    def scopes(self) -> Any:
        return incident_scopes(self.records, tenants=TENANTS)

    def incident(self, view_id: str = VIEW_ID) -> Incident | None:
        store = record_incident_store(self.records, tenants=TENANTS)
        return asyncio.run(store.get(incident_id_for(f"slack:{SLACK_TENANT}:{view_id}"))).data


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    world = World(
        records=SwitchableRecordStore(),
        reports=InMemoryIncidentReport(next_ids=["D0REPORT", "D0REPORT2"], placements=PLACEMENTS),
        conversations=InMemoryIncidentConversation(tenant=SLACK_TENANT),
        sink=RecordingSink(),
        reply=FakeSlackReply(),
    )
    monkeypatch.setattr(providers, "incident_report", lambda: world.reports)
    monkeypatch.setattr(providers, "incident_list_projection", InMemoryIncidentListProjection)
    monkeypatch.setattr(providers, "incident_conversation", lambda: world.conversations)
    monkeypatch.setattr(providers, "video_call", InMemoryVideoCall)
    monkeypatch.setattr(providers, "placement_schedule_lookup", InMemoryPlacementScheduleLookup)
    monkeypatch.setattr(providers, "oncall_lookup", lambda: InMemoryOnCallLookup(people={}))
    monkeypatch.setattr(providers, "declare_event_sink", lambda: world.sink)
    yield world


def _payload(text: str = "", *, trigger_id: str = "T0TRIGGER", locale: str = "en-US") -> CommandPayload:
    return CommandPayload(
        text=text,
        user_id=USER,
        user_email=None,
        channel_id="C0HERE",
        user_locale=locale,
        response_url=None,
        platform_metadata={"trigger_id": trigger_id} if trigger_id else {},
    )


def _submission(
    name: str,
    *,
    view_id: str = VIEW_ID,
    severity: str = "sev-2",
    security: str = "no",
    policy_help: str = "no",
    product: tuple[str, str] | None = ("F0FORMS", "Forms"),
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "name": {"name": {"value": name}},
        "severity": {"severity": {"selected_option": {"value": severity}}},
        "security_incident": {"security_incident": {"selected_option": {"value": security}}},
        "policy_help": {"policy_help": {"selected_option": {"value": policy_help}}},
    }
    if product is not None:
        values["product"] = {"product": {"selected_option": {"text": {"text": product[1]}, "value": product[0]}}}
    return {
        "trigger_id": "T0SUBMIT",
        "user": {"id": USER},
        "view": {
            "id": view_id,
            "callback_id": DECLARE_CALLBACK_ID,
            "private_metadata": "",
            "blocks": [{"block_id": "locale", "elements": [{"value": "en-US"}]}],
            "state": {"values": values},
        },
    }


def _block_ids(view: dict[str, Any]) -> list[str]:
    return [block["block_id"] for block in view["blocks"] if "block_id" in block]


# Registration


def test_register_declare_registers_the_root_command_the_form_and_the_alert_buttons_with_their_legacy_ids() -> None:
    registrar = FakeSlackRegistrar(service_scopes=incident_scopes(tenants=TENANTS))

    register_declare(registrar, registrar.service_scopes)

    assert registrar.command("incident", parent=None)["description_key"] == "incident_response.declare.description"
    assert DECLARE_CALLBACK_ID in registrar.view_submissions
    assert LOCALE_ACTION_ID in registrar.block_actions
    assert ALERT_BUTTONS_CALLBACK_ID in registrar.attachment_actions
    assert registrar.legacy_ids == {
        LEGACY_LOCALE_ACTION_ID: LOCALE_ACTION_ID,
        LEGACY_ALERT_BUTTONS_CALLBACK_ID: ALERT_BUTTONS_CALLBACK_ID,
    }


# /incident


def test_the_command_opens_the_loading_view_then_the_form_with_the_placements(world: World) -> None:
    response = handle_declare_command(_payload("db down"), world.reply, world.scopes)

    assert (response.message, response.ephemeral) == ("", True)
    [opened] = world.reply.calls_to("open_view")
    assert opened["trigger_id"] == "T0TRIGGER"
    [updated] = world.reply.calls_to("update_view")
    assert updated["view_id"] == "view-id-canned"
    product = next(block for block in updated["view"]["blocks"] if block.get("block_id") == "product")
    assert [option["value"] for option in product["element"]["options"]] == ["F0FORMS", "F0PAYMENTS"]


def test_the_command_without_a_trigger_answers_privately_and_opens_nothing(world: World) -> None:
    response = handle_declare_command(_payload(trigger_id="", locale="fr-FR"), world.reply, world.scopes)

    assert response.message == "Impossible d'ouvrir le formulaire d'incident. Veuillez réessayer."
    assert world.reply.calls == []


def test_a_view_that_fails_to_open_answers_privately(world: World) -> None:
    world.reply.result = OperationResult.transient_error("rate limited")

    response = handle_declare_command(_payload(), world.reply, world.scopes)

    assert response.message == "Couldn't open the incident form. Please try again."
    assert world.reply.calls_to("update_view") == []


def test_placements_that_cannot_be_listed_leave_the_product_out(world: World) -> None:
    world.reports = InMemoryIncidentReport(folder_id="")

    handle_declare_command(_payload(), world.reply, world.scopes)

    [updated] = world.reply.calls_to("update_view")
    assert "product" not in _block_ids(updated["view"])


# The locale toggle


def test_the_toggle_rerenders_the_form_in_french_keeping_the_name(world: World) -> None:
    body = {
        "actions": [{"value": "en-US"}],
        "view": {"id": VIEW_ID, "private_metadata": "meta", "state": {"values": {"name": {"name": {"value": "db down"}}}}},
    }
    ack = Ack()

    handle_locale_toggle(ack, body, world.reply)

    assert ack.calls == [{}]
    [updated] = world.reply.calls_to("update_view")
    form = updated["view"]
    assert (updated["view_id"], form["private_metadata"], form["title"]["text"]) == (VIEW_ID, "meta", "IFS - Lancer un incident")
    name = next(block for block in form["blocks"] if block.get("block_id") == "name")
    assert name["element"]["initial_value"] == "db down"


# The submission


def test_a_valid_submission_acks_once_and_records_the_incident_with_the_declarer_as_commander(world: World) -> None:
    ack = Ack()

    handle_declare_submission(ack, _submission("db down", security="yes"), world.reply, world.scopes)

    assert ack.calls == [{}]
    incident = world.incident()
    assert incident is not None
    assert (incident.title, incident.security_incident, incident.severity) == ("db down", True, Severity.SEV2)
    assert (incident.declared_by, incident.incident_commander) == (USER, USER)
    assert incident.conversation is not None
    [success] = world.reply.calls_to("open_view")
    assert success["trigger_id"] == "T0SUBMIT"
    assert world.sink.events == [("incident_called", {"user_id": USER, "view_id": VIEW_ID})]


def test_sev0_is_recorded_as_sev0_not_as_unrated(world: World) -> None:
    handle_declare_submission(Ack(), _submission("db down", severity="sev-0"), world.reply, world.scopes)

    incident = world.incident()
    assert incident is not None and incident.severity is Severity.SEV0


def test_none_is_unrated(world: World) -> None:
    handle_declare_submission(Ack(), _submission("db down", severity="none"), world.reply, world.scopes)

    incident = world.incident()
    assert incident is not None and incident.severity is None


def test_the_chosen_product_files_the_report_in_its_placement(world: World) -> None:
    handle_declare_submission(Ack(), _submission("db down", product=("F0PAYMENTS", "Payments")), world.reply, world.scopes)

    incident = world.incident()
    assert incident is not None and incident.report is not None
    assert world.reports.filed_in(incident.report) == "F0PAYMENTS"


def test_a_redelivered_submission_is_the_same_incident(world: World) -> None:
    handle_declare_submission(Ack(), _submission("db down"), world.reply, world.scopes)
    handle_declare_submission(Ack(), _submission("db down"), world.reply, world.scopes)

    assert len(world.conversations.created_names) == 1
    assert world.incident() is not None


@pytest.mark.parametrize(
    ("name", "error"),
    [
        (
            "",
            "Description must only contain number and letters // La description ne doit contenir que des nombres et des lettres",
        ),
        (
            "db/down",
            "Description must only contain number and letters // La description ne doit contenir que des nombres et des lettres",
        ),
        ("a" * 60, "Description must be less than 60 characters // La description doit contenir moins de 60 caractères"),
    ],
)
def test_an_invalid_name_acks_once_with_the_field_error_and_declares_nothing(world: World, name: str, error: str) -> None:
    ack = Ack()

    handle_declare_submission(ack, _submission(name), world.reply, world.scopes)

    assert ack.calls == [{"response_action": "errors", "errors": {"name": error}}]
    assert world.incident() is None
    assert world.reply.calls == []


def test_a_name_with_accented_letters_is_valid(world: World) -> None:
    handle_declare_submission(Ack(), _submission("Panne réseau"), world.reply, world.scopes)

    incident = world.incident()
    assert incident is not None and incident.title == "Panne réseau"


def test_a_record_that_cannot_be_written_tells_the_declarer_and_creates_nothing(world: World) -> None:
    world.records.go_down()

    handle_declare_submission(Ack(), _submission("db down"), world.reply, world.scopes)

    assert world.conversations.created_names == []
    assert [(call["channel_id"], call["text"]) for call in world.reply.calls_to("post_message")] == [
        (USER, ":warning: The incident could not be recorded. Please submit the form again or contact the SRE team.")
    ]
    assert world.reply.calls_to("open_view") == []


def test_a_submission_without_a_product_files_the_report_in_the_default_folder(world: World) -> None:
    handle_declare_submission(Ack(), _submission("db down", product=None), world.reply, world.scopes)

    incident = world.incident()
    assert incident is not None and incident.report is not None
    assert world.reports.filed_in(incident.report) == "F0INCIDENTS"


def test_the_placement_carries_the_google_tenant(world: World) -> None:
    placements: list[ReportPlacement | None] = []
    original = world.reports.create_from_template

    async def spy(title: str, placement: ReportPlacement | None = None) -> Any:
        placements.append(placement)
        return await original(title, placement)

    world.reports.create_from_template = spy  # type: ignore[method-assign]

    handle_declare_submission(Ack(), _submission("db down"), world.reply, world.scopes)

    assert placements == [
        ReportPlacement(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="F0FORMS", label="Forms")
    ]


def test_policy_help_invites_the_configured_policy_group(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_incident_response_settings(), "policy_group_id", "S0POLICY")
    world.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, groups={"S0POLICY": ["U0POLICY"]})

    handle_declare_submission(Ack(), _submission("db down", policy_help="yes"), world.reply, world.scopes)

    incident = world.incident()
    assert incident is not None and incident.conversation is not None
    assert world.conversations.invited_to(incident.conversation) == (USER, "U0POLICY")


def test_without_policy_help_the_policy_group_is_not_invited(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_incident_response_settings(), "policy_group_id", "S0POLICY")
    world.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, groups={"S0POLICY": ["U0POLICY"]})

    handle_declare_submission(Ack(), _submission("db down"), world.reply, world.scopes)

    incident = world.incident()
    assert incident is not None and incident.conversation is not None
    assert world.conversations.invited_to(incident.conversation) == (USER,)
