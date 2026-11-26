"""The ``/sre incident roles manage`` command and the roles modal's submission.

The handlers run over a scope opener resolving an in-memory record store seeded with one legacy
incident on the channel (its report linked, Slack and Google configured); the response providers
return the core in-memory conversation and legacy roles reader. The modal is read from the fake
reply's recorded ``open_view`` and submitted through its own block and action ids. The modal and
replies are read in the invoker's language and the announcements in the instance languages
(English then French unless a test configures them), from the real catalogues, which the
directory's conftest loads. Assertions read what the invoker sees (the view, the private notice), the stored
roles and the channel's posts and purpose.
"""

import asyncio
import json
from typing import Any

import pytest

from contracts.operations.result import OperationResult
from contracts.slack.models import CommandPayload
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.adapters.in_memory import InMemoryIncidentConversation, InMemoryLegacyRolesReader
from features.incident.core.api import ReportReference
from features.incident.response import providers
from features.incident.response.entrypoints.slack_roles import (
    ROLES_ACTION_ID,
    ROLES_CALLBACK_ID,
    handle_roles_manage_command,
    handle_roles_submission,
    register_roles,
)
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import (
    GOOGLE_TENANT,
    SLACK_TENANT,
    SwitchableRecordStore,
    incident_scopes,
    record_incident_store,
    seed_legacy_incident,
    slack_conversation,
)
from tests.factories.slack import FakeSlackRegistrar, FakeSlackReply

pytestmark = pytest.mark.unit

CHANNEL_ID = "C0INCIDENT"
USER_ID = "U0INVOKER"
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="D0REPORT")
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}
BLOCK = {role: f"incident.response.roles.{role.value}" for role in IncidentRole}
IC, OL, COMMS = IncidentRole.INCIDENT_COMMANDER, IncidentRole.OPERATIONS_LEAD, IncidentRole.COMMUNICATIONS_LEAD


class _Client:
    """The Bolt web client, recording the private notices the submission posts."""

    def __init__(self) -> None:
        self.ephemerals: list[dict[str, Any]] = []

    def chat_postEphemeral(self, **kwargs: Any) -> dict[str, Any]:  # noqa: N802 -- Slack's method name
        self.ephemerals.append(kwargs)
        return {"ok": True}


class _Surface:
    """The records, the fakes behind the response providers, the reply and the client."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, records: InMemoryRecordStore | None = None) -> None:
        self.records = InMemoryRecordStore() if records is None else records
        seed_legacy_incident(
            self.records, CHANNEL_ID, incident_id="inc-1", report_url="https://docs.google.com/document/d/D0REPORT/edit"
        )
        self.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, open_ids=[CHANNEL_ID])
        self.conversations.seed_purpose(slack_conversation(CHANNEL_ID), "Checkout outage")
        self.legacy = InMemoryLegacyRolesReader()
        self.legacy.seed(REPORT, {IC: "U0OLDIC", OL: "U0OLDOL"})
        self.reply = FakeSlackReply()
        self.client = _Client()
        self.scopes = incident_scopes(self.records, tenants=TENANTS)
        monkeypatch.setattr(providers, "incident_conversation", lambda: self.conversations)
        monkeypatch.setattr(providers, "legacy_roles_reader", lambda: self.legacy)

    def manage(self, *, locale: str = "en-US", channel_id: str = CHANNEL_ID, trigger_id: str = "T0TRIGGER") -> Any:
        metadata = {"channel_name": "incident-2026-10-checkout"}
        if trigger_id:
            metadata["trigger_id"] = trigger_id
        payload = CommandPayload(
            text="manage", user_id=USER_ID, channel_id=channel_id, user_locale=locale, platform_metadata=metadata
        )
        return handle_roles_manage_command(payload, self.reply, self.scopes)

    def view(self) -> dict[str, Any]:
        [opened] = self.reply.calls_to("open_view")
        view: dict[str, Any] = opened["view"]
        return view

    def submit(self, view: dict[str, Any], picks: dict[IncidentRole, str | None]) -> list[tuple[str, dict[str, Any]]]:
        """Submit ``view`` with ``picks`` over what it preselected; return the ack calls."""
        values: dict[str, Any] = {}
        for block in view["blocks"]:
            if block["type"] != "input":
                continue
            role = next(role for role, block_id in BLOCK.items() if block_id == block["block_id"])
            picked = picks[role] if role in picks else block["element"].get("initial_user")
            values[block["block_id"]] = {ROLES_ACTION_ID: {"type": "users_select", "selected_user": picked}}
        acks: list[tuple[str, dict[str, Any]]] = []

        def ack(**kwargs: Any) -> None:
            acks.append(("ack", kwargs))

        body = {
            "user": {"id": USER_ID},
            "view": {
                "callback_id": view["callback_id"],
                "private_metadata": view["private_metadata"],
                "state": {"values": values},
            },
        }
        handle_roles_submission(ack, body, self.client, self.scopes)
        return acks

    def stored(self) -> dict[IncidentRole, str | None]:
        found = asyncio.run(record_incident_store(self.records, tenants=TENANTS).get("inc-1"))
        assert found.data is not None
        return {role: getattr(found.data, role.value) for role in IncidentRole}

    def posts(self) -> tuple[str, ...]:
        return tuple(self.conversations.posts_in(slack_conversation(CHANNEL_ID)))

    def purpose(self) -> str | None:
        return self.conversations.purpose_of(slack_conversation(CHANNEL_ID))


@pytest.fixture
def surface(monkeypatch: pytest.MonkeyPatch) -> _Surface:
    return _Surface(monkeypatch)


def _pickers(view: dict[str, Any]) -> list[dict[str, Any]]:
    return [block for block in view["blocks"] if block["type"] == "input"]


def test_the_command_opens_five_pickers_with_the_commander_and_lead_required(surface: _Surface) -> None:
    response = surface.manage()

    assert (response.message, response.ephemeral) == ("", True)
    [opened] = surface.reply.calls_to("open_view")
    assert opened["trigger_id"] == "T0TRIGGER"
    view = surface.view()
    assert view["callback_id"] == ROLES_CALLBACK_ID
    assert [(block["block_id"], block["optional"]) for block in _pickers(view)] == [
        (BLOCK[IC], False),
        (BLOCK[OL], False),
        (BLOCK[COMMS], True),
        (BLOCK[IncidentRole.POLICY_LEAD], True),
        (BLOCK[IncidentRole.POSTMORTEM_OWNER], True),
    ]
    assert {block["element"]["action_id"] for block in _pickers(view)} == {ROLES_ACTION_ID}


def test_the_header_names_the_incident_without_the_channel_prefix(surface: _Surface) -> None:
    surface.manage()

    assert surface.view()["blocks"][0]["text"]["text"] == "Roles for 2026-10-checkout"


def test_a_french_invoker_reads_the_modal_in_french(surface: _Surface) -> None:
    surface.manage(locale="fr-FR")

    view = surface.view()
    assert view["title"]["text"] == "SRE - Gestion des rôles"
    assert _pickers(view)[0]["label"]["text"] == "Commandant d'incident"
    assert json.loads(view["private_metadata"])["locale"] == "fr-FR"


def test_roles_on_the_record_are_preselected_over_the_legacy_report(surface: _Surface) -> None:
    asyncio.run(
        record_incident_store(surface.records, tenants=TENANTS).set_roles("inc-1", {IncidentRole.POLICY_LEAD: "U0POLICY"})
    )

    surface.manage()

    selected = {block["block_id"]: block["element"].get("initial_user") for block in _pickers(surface.view())}
    assert selected == {
        BLOCK[IC]: None,
        BLOCK[OL]: None,
        BLOCK[COMMS]: None,
        BLOCK[IncidentRole.POLICY_LEAD]: "U0POLICY",
        BLOCK[IncidentRole.POSTMORTEM_OWNER]: None,
    }


def test_an_incident_with_no_role_on_the_record_shows_the_legacy_report_roles(surface: _Surface) -> None:
    surface.manage()

    selected = {block["block_id"]: block["element"].get("initial_user") for block in _pickers(surface.view())}
    assert (selected[BLOCK[IC]], selected[BLOCK[OL]]) == ("U0OLDIC", "U0OLDOL")


def test_a_channel_that_is_not_an_incident_gets_a_private_reply_and_no_view(surface: _Surface) -> None:
    response = surface.manage(channel_id="C0OTHER")

    assert response.message == "This channel is not an incident channel, so it has no roles to manage."
    assert surface.reply.calls_to("open_view") == []


def test_without_a_trigger_id_nothing_opens(surface: _Surface) -> None:
    response = surface.manage(trigger_id="")

    assert response.message == "Couldn't open the roles window. Please try again."
    assert surface.reply.calls_to("open_view") == []


def test_a_view_that_cannot_open_is_told_to_the_invoker(monkeypatch: pytest.MonkeyPatch) -> None:
    surface = _Surface(monkeypatch)
    surface.reply = FakeSlackReply(OperationResult.transient_error("trigger expired"))

    assert surface.manage().message == "Couldn't open the roles window. Please try again."


def test_with_the_records_unavailable_the_modal_does_not_open(monkeypatch: pytest.MonkeyPatch) -> None:
    records = SwitchableRecordStore()
    surface = _Surface(monkeypatch, records)
    records.go_down()

    response = surface.manage()

    assert response.message == "The incidents database is temporarily unavailable. Please try again later."
    assert surface.reply.calls_to("open_view") == []


def test_submitting_writes_the_five_roles_announces_each_change_and_sets_the_purpose(surface: _Surface) -> None:
    surface.manage()

    acks = surface.submit(surface.view(), {IC: "U0NEWIC", OL: "U0NEWOL", COMMS: "U0COMMS"})

    assert acks == [("ack", {})]
    assert surface.stored() == {
        IC: "U0NEWIC",
        OL: "U0NEWOL",
        COMMS: "U0COMMS",
        IncidentRole.POLICY_LEAD: None,
        IncidentRole.POSTMORTEM_OWNER: None,
    }
    assert surface.posts() == (
        "<@U0NEWIC> has been assigned as incident commander for this incident.\n"
        "<@U0NEWIC> a été désigné(e) commandant d'incident pour cet incident.",
        "<@U0NEWOL> has been assigned as operations lead for this incident.\n"
        "<@U0NEWOL> a été désigné(e) responsable des opérations pour cet incident.",
        "<@U0COMMS> has been assigned as communications lead for this incident.\n"
        "<@U0COMMS> a été désigné(e) responsable des communications pour cet incident.",
    )
    assert surface.purpose() == "Checkout outage \nIC: <@U0NEWIC> / OL: <@U0NEWOL>"
    assert surface.client.ephemerals == []


def test_a_french_submitters_announcement_is_in_the_instance_languages(surface: _Surface) -> None:
    surface.manage(locale="fr-FR")

    surface.submit(surface.view(), {IC: "U0NEWIC"})

    assert surface.posts() == (
        "<@U0NEWIC> has been assigned as incident commander for this incident.\n"
        "<@U0NEWIC> a été désigné(e) commandant d'incident pour cet incident.",
    )


def test_the_announcements_follow_the_instance_language_order(surface: _Surface) -> None:
    surface.scopes = incident_scopes(surface.records, tenants=TENANTS, languages=("fr-FR", "en-US"))
    surface.manage()

    surface.submit(surface.view(), {IC: "U0NEWIC"})

    assert surface.posts() == (
        "<@U0NEWIC> a été désigné(e) commandant d'incident pour cet incident.\n"
        "<@U0NEWIC> has been assigned as incident commander for this incident.",
    )


def test_an_instance_with_one_language_announces_in_one_line(surface: _Surface) -> None:
    surface.scopes = incident_scopes(surface.records, tenants=TENANTS, languages=("en-US",))
    surface.manage(locale="fr-FR")

    surface.submit(surface.view(), {IC: "U0NEWIC"})

    assert surface.posts() == ("<@U0NEWIC> has been assigned as incident commander for this incident.",)


def test_a_french_submitters_private_notice_stays_in_french(surface: _Surface) -> None:
    surface.manage(locale="fr-FR")
    surface.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, archived_ids=[CHANNEL_ID])

    surface.submit(surface.view(), {IC: "U0NEWIC"})

    [notice] = surface.client.ephemerals
    assert notice["text"] == (
        "Impossible d'écrire dans le canal de l'incident; les rôles sont enregistrés, mais rien n'y a été publié ni modifié."
    )


def test_an_unsupported_user_locale_opens_the_modal_in_the_first_instance_language(surface: _Surface) -> None:
    surface.scopes = incident_scopes(surface.records, tenants=TENANTS, languages=("fr-FR", "en-US"))

    surface.manage(locale="de-DE")

    assert json.loads(surface.view()["private_metadata"])["locale"] == "fr-FR"


def test_a_missing_commander_is_a_field_error_and_writes_nothing(surface: _Surface) -> None:
    surface.manage()

    acks = surface.submit(surface.view(), {IC: None})

    assert acks == [("ack", {"response_action": "errors", "errors": {BLOCK[IC]: "Please select a user."}})]
    assert surface.stored()[OL] is None
    assert surface.posts() == ()


def test_a_submission_for_a_channel_that_is_not_an_incident_tells_the_submitter_privately(surface: _Surface) -> None:
    surface.manage()
    view = {**surface.view(), "private_metadata": json.dumps({"channel_id": "C0OTHER", "locale": "en-US"})}

    surface.submit(view, {IC: "U0NEWIC"})

    assert surface.client.ephemerals == [
        {
            "channel": "C0OTHER",
            "user": USER_ID,
            "text": "This channel is not an incident channel, so it has no roles to manage.",
        }
    ]
    assert surface.posts() == ()


def test_a_channel_that_cannot_be_written_to_keeps_the_roles_and_says_so_privately(surface: _Surface) -> None:
    surface.manage()
    surface.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, archived_ids=[CHANNEL_ID])

    surface.submit(surface.view(), {IC: "U0NEWIC"})

    assert surface.stored()[IC] == "U0NEWIC"
    [notice] = surface.client.ephemerals
    assert notice["text"].startswith("The incident channel can't be written to")


def test_the_registration_names_the_commands_and_the_modal() -> None:
    registrar = FakeSlackRegistrar(service_scopes=incident_scopes(tenants=TENANTS))

    register_roles(registrar, registrar.service_scopes)

    assert [(command["parent"], command["command"], command["handler"] is None) for command in registrar.commands] == [
        ("sre.incident", "roles", True),
        ("sre.incident.roles", "manage", False),
    ]
    assert list(registrar.view_submissions) == [ROLES_CALLBACK_ID]
