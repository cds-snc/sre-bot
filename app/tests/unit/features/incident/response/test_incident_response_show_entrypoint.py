"""``/sre incident show``, its Update buttons and the update modal's submission.

The handlers run over a scope opener resolving an in-memory record store seeded with one
legacy incident on the channel (severity sev-2, its report and Meet links; Slack and Google
configured); the response providers return the core in-memory report, list projection,
conversation, video call and legacy roles reader. Views are read from the fake reply's
recorded ``open_view``, ``push_view`` and ``update_view`` calls and answered through the ids
they carry. Replies are read in the invoker's or the modal's locale from the real
catalogues, which the directory's conftest loads. Assertions read what users see (the views,
the private lines, the channel's posts) and the stored record.

Authorization: none beyond the command check (the channel's incident), as every response write.
"""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.slack.models import CommandPayload
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentRole, IncidentStatus, Severity
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentListProjection,
    InMemoryIncidentReport,
    InMemoryLegacyRolesReader,
    InMemoryVideoCall,
)
from features.incident.core.api import Incident, ReportReference
from features.incident.response import providers
from features.incident.response.entrypoints.slack_show import (
    handle_show_command,
    handle_update_press,
    handle_update_submission,
    register_show,
)
from features.incident.response.entrypoints.slack_show_views import (
    FIELD_CALLBACK_ID,
    SELECT_BLOCK_ID,
    UPDATE_ACTION_ID,
    VALUE_ACTION_ID,
    WHEN_BLOCK_ID,
)
from tests.factories.incident import (
    GOOGLE_TENANT,
    SLACK_TENANT,
    SwitchableRecordStore,
    incident_on,
    incident_scopes,
    record_incident_store,
    seed_legacy_incident,
    slack_conversation,
)
from tests.factories.slack import FakeSlackRegistrar, FakeSlackReply

pytestmark = pytest.mark.unit

CHANNEL_ID = "C0INCIDENT"
USER_ID = "U0INVOKER"
REPORT_URL = "https://docs.google.com/document/d/D0REPORT/edit"
MEET_URL = "https://meet.google.com/abc-defg-hij"
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="D0REPORT")
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}
ROOT_VIEW_ID = "V0ROOT"


class _Surface:
    """The records, the fakes behind the response providers and the reply sender."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, reply: FakeSlackReply | None = None, *, languages: tuple[str, ...] | None = None
    ) -> None:
        self.records = SwitchableRecordStore()
        seed_legacy_incident(
            self.records,
            CHANNEL_ID,
            incident_id="inc-1",
            report_url=REPORT_URL,
            name="Checkout outage",
            severity="sev-2",
            meet_url=MEET_URL,
        )
        self.reports = InMemoryIncidentReport(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0")
        self.reports.seed_sections(REPORT, [])
        asyncio.run(self.reports.set_status_text(REPORT, IncidentStatus.OPEN))
        self.projection = InMemoryIncidentListProjection()
        asyncio.run(self.projection.append_row(replace(incident_on(CHANNEL_ID, "inc-1"), report=REPORT)))
        self.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, open_ids=[CHANNEL_ID])
        self.legacy = InMemoryLegacyRolesReader()
        self.legacy.seed(REPORT, {IncidentRole.INCIDENT_COMMANDER: "U0OLDIC"})
        self.reply = reply or FakeSlackReply()
        self.scopes = incident_scopes(self.records, tenants=TENANTS, languages=languages)
        monkeypatch.setattr(providers, "incident_report", lambda: self.reports)
        monkeypatch.setattr(providers, "incident_list_projection", lambda: self.projection)
        monkeypatch.setattr(providers, "incident_conversation", lambda: self.conversations)
        monkeypatch.setattr(providers, "legacy_roles_reader", lambda: self.legacy)
        monkeypatch.setattr(providers, "video_call", InMemoryVideoCall)

    def show(self, *, locale: str = "en-US", channel_id: str = CHANNEL_ID, trigger_id: str = "T0TRIGGER") -> Any:
        metadata = {"trigger_id": trigger_id} if trigger_id else {}
        payload = CommandPayload(text="", user_id=USER_ID, channel_id=channel_id, user_locale=locale, platform_metadata=metadata)
        return handle_show_command(payload, self.reply, self.scopes)

    def info(self) -> dict[str, Any]:
        [opened] = self.reply.calls_to("open_view")
        view: dict[str, Any] = opened["view"]
        return view

    def press(self, field: str, info: dict[str, Any] | None = None) -> list[str]:
        """Press the Update button of ``field``; return the ack calls."""
        acks: list[str] = []
        body = {
            "trigger_id": "T0CLICK",
            "user": {"id": USER_ID},
            "actions": [{"action_id": UPDATE_ACTION_ID, "value": field}],
            "view": {"id": "V0INFO", "root_view_id": ROOT_VIEW_ID, "private_metadata": (info or self.info())["private_metadata"]},
        }
        handle_update_press(lambda **_: acks.append("ack"), body, self.reply, self.scopes)
        return acks

    def pushed(self) -> dict[str, Any]:
        view: dict[str, Any] = self.reply.calls_to("push_view")[-1]["view"]
        return view

    def submit(self, view: dict[str, Any], *, option: str | None = None, instant: int | None = None) -> list[str]:
        """Submit the pushed field view with a selected option or a picked instant; return the ack calls."""
        values: dict[str, Any] = {}
        if option is not None:
            values[SELECT_BLOCK_ID] = {VALUE_ACTION_ID: {"type": "static_select", "selected_option": {"value": option}}}
        if instant is not None:
            values[WHEN_BLOCK_ID] = {VALUE_ACTION_ID: {"type": "datetimepicker", "selected_date_time": instant}}
        acks: list[str] = []
        body = {
            "user": {"id": USER_ID},
            "view": {
                "id": "V0FIELD",
                "root_view_id": ROOT_VIEW_ID,
                "callback_id": view["callback_id"],
                "private_metadata": view["private_metadata"],
                "state": {"values": values},
            },
        }
        handle_update_submission(lambda **_: acks.append("ack"), body, self.reply, self.scopes)
        return acks

    def update(self, field: str, **answer: Any) -> None:
        self.show()
        self.press(field)
        self.submit(self.pushed(), **answer)

    def stored(self) -> Incident:
        found = asyncio.run(record_incident_store(self.records, tenants=TENANTS).get("inc-1"))
        assert found.data is not None
        return found.data

    def posts(self) -> tuple[str, ...]:
        return tuple(self.conversations.posts_in(slack_conversation(CHANNEL_ID)))

    def private_lines(self) -> list[str]:
        return [call["text"] for call in self.reply.calls_to("post_ephemeral")]


@pytest.fixture
def surface(monkeypatch: pytest.MonkeyPatch) -> _Surface:
    return _Surface(monkeypatch)


def _text(view: dict[str, Any]) -> str:
    lines = []
    for block in view["blocks"]:
        lines.append(block.get("text", {}).get("text", ""))
        lines.extend(field_["text"] for field_ in block.get("fields", []))
    return "\n".join(lines)


def _buttons(view: dict[str, Any]) -> dict[str, str]:
    return {block["accessory"]["value"]: block["accessory"]["action_id"] for block in view["blocks"] if "accessory" in block}


# Registration


def test_show_registers_its_command_button_and_submission_under_the_plugin_prefix() -> None:
    registrar = FakeSlackRegistrar()

    register_show(registrar, incident_scopes())

    [command] = registrar.commands
    assert (command["command"], command["parent"]) == ("show", "sre.incident")
    assert list(registrar.block_actions) == [UPDATE_ACTION_ID]
    assert list(registrar.view_submissions) == [FIELD_CALLBACK_ID]
    assert all(name.startswith("incident.response.") for name in [*registrar.block_actions, *registrar.view_submissions])


# /sre incident show


def test_show_opens_the_information_modal_from_the_record(surface: _Surface) -> None:
    response = surface.show()

    assert (response.message, response.ephemeral) == ("", True)
    view = surface.info()
    text = _text(view)
    assert view["blocks"][0]["text"]["text"] == "Checkout outage"
    assert "*ID*: inc-1" in text
    assert f"<{REPORT_URL}|:memo: Incident Report>" in text
    assert f"<{MEET_URL}|:headphones: Google Meet>" in text
    assert "*Severity*:\nsev-2" in text
    assert "*Status*:\nOpen" in text
    assert "*Security Incident*:\nNo" in text
    assert "*Detection Time*:\nUnknown" in text
    assert "Retro" not in text
    assert set(_buttons(view)) == {
        "severity",
        "status",
        "security_incident",
        "detection_time",
        "start_impact_time",
        "end_impact_time",
    }
    assert set(_buttons(view).values()) == {UPDATE_ACTION_ID}
    assert json.loads(view["private_metadata"]) == {"channel_id": CHANNEL_ID, "locale": "en-US"}


def test_show_lists_the_five_roles_reading_the_report_when_the_record_holds_none(surface: _Surface) -> None:
    surface.show()

    text = _text(surface.info())
    assert "*Incident Commander*:\n<@U0OLDIC>" in text
    assert "*Operations Lead*:\nUnassigned" in text
    assert "*Postmortem Owner*:\nUnassigned" in text


def test_show_renders_in_the_invokers_locale(surface: _Surface) -> None:
    surface.show(locale="fr-FR")

    view = surface.info()
    assert view["title"]["text"] == "Information sur l'incident"
    assert "*Sévérité*:\nsev-2" in _text(view)
    assert json.loads(view["private_metadata"])["locale"] == "fr-FR"


def test_show_outside_an_incident_channel_opens_nothing_and_says_why(surface: _Surface) -> None:
    response = surface.show(channel_id="C0OTHER")

    assert surface.reply.calls_to("open_view") == []
    assert response.message == "This command is only available in incident channels. No incident records found for this channel."


def test_show_with_the_store_down_answers_in_the_invokers_locale_only(surface: _Surface) -> None:
    surface.records.go_down()

    response = surface.show()

    assert response.message == "The incidents database is temporarily unavailable. Please try again later."


def test_show_without_a_trigger_or_with_a_failed_open_says_the_window_did_not_open(monkeypatch: pytest.MonkeyPatch) -> None:
    failing = _Surface(monkeypatch, FakeSlackReply(OperationResult.permanent_error("expired", error_code="expired_trigger_id")))

    assert failing.show(trigger_id="").message == "Couldn't open the incident information window. Please try again."
    assert failing.show().message == "Couldn't open the incident information window. Please try again."


# Update buttons


def test_pressing_update_acks_and_pushes_a_select_on_the_current_value(surface: _Surface) -> None:
    surface.show()

    assert surface.press("severity") == ["ack"]

    [pushed] = surface.reply.calls_to("push_view")
    assert pushed["trigger_id"] == "T0CLICK"
    [field_input] = [block for block in pushed["view"]["blocks"] if block["type"] == "input"]
    element = field_input["element"]
    assert element["initial_option"]["value"] == "sev-2"
    assert [option["value"] for option in element["options"]] == ["none", "sev-0", "sev-1", "sev-2", "sev-3", "sev-4"]
    assert pushed["view"]["callback_id"] == FIELD_CALLBACK_ID


def test_pressing_a_time_pushes_one_date_and_time_picker(surface: _Surface) -> None:
    surface.show()

    surface.press("detection_time")

    [field_input] = [block for block in surface.pushed()["blocks"] if block["type"] == "input"]
    assert field_input["element"]["type"] == "datetimepicker"
    assert "initial_date_time" not in field_input["element"]


def test_pressing_an_unknown_field_acks_and_pushes_nothing(surface: _Surface) -> None:
    surface.show()

    assert surface.press("retrospective_url") == ["ack"]

    assert surface.reply.calls_to("push_view") == []


def test_a_press_after_the_incident_became_unreadable_is_refused_privately(surface: _Surface) -> None:
    surface.show()
    surface.records.go_down()

    surface.press("severity")

    assert surface.reply.calls_to("push_view") == []
    assert surface.private_lines() == ["The incidents database is temporarily unavailable. Please try again later."]


# Submission


def test_submitting_a_severity_writes_the_record_tells_the_channel_in_both_languages_and_refreshes_the_modal(
    surface: _Surface,
) -> None:
    surface.show()
    surface.press("severity")

    assert surface.submit(surface.pushed(), option="sev-1") == ["ack"]

    assert surface.stored().severity is Severity.SEV1
    assert surface.posts() == (
        f"<@{USER_ID}> has updated the field severity to sev-1\n<@{USER_ID}> a mis à jour le champ severity à sev-1",
    )
    [refreshed] = surface.reply.calls_to("update_view")
    assert refreshed["view_id"] == ROOT_VIEW_ID
    assert "*Severity*:\nsev-1" in _text(refreshed["view"])


def test_the_field_notice_follows_the_instance_languages_and_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """A French-first instance posts French first; the submitter's English modal is not what decides it (decisions/languages.md)."""
    surface = _Surface(monkeypatch, languages=("fr-FR", "en-US"))

    surface.update("severity", option="sev-1")

    assert surface.posts() == (
        f"<@{USER_ID}> a mis à jour le champ severity à sev-1\n<@{USER_ID}> has updated the field severity to sev-1",
    )


def test_a_one_language_instance_posts_the_field_notice_in_that_language_only(monkeypatch: pytest.MonkeyPatch) -> None:
    surface = _Surface(monkeypatch, languages=("en-US",))

    surface.update("severity", option="sev-1")

    assert surface.posts() == (f"<@{USER_ID}> has updated the field severity to sev-1",)


def test_a_regional_locale_is_answered_in_its_language_not_a_raw_key(surface: _Surface) -> None:
    """A Canadian French client is matched to fr-FR on its language (RFC 4647 lookup)."""
    surface.records.go_down()

    response = surface.show(locale="fr-CA")

    assert response.message == "La base de données des incidents est temporairement indisponible. Veuillez réessayer plus tard."


def test_an_unsupported_locale_is_answered_in_the_first_instance_language(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spanish has no catalogue: a French-first instance answers in French rather than showing the key."""
    surface = _Surface(monkeypatch, languages=("fr-FR", "en-US"))
    surface.records.go_down()

    response = surface.show(locale="es-ES")

    assert response.message == "La base de données des incidents est temporairement indisponible. Veuillez réessayer plus tard."


def test_submitting_none_clears_the_severity(surface: _Surface) -> None:
    surface.update("severity", option="none")

    assert surface.stored().severity is None


def test_submitting_a_time_stores_the_picked_instant_and_names_it_with_a_date_token(surface: _Surface) -> None:
    instant = int(datetime(2026, 10, 1, 13, 30, tzinfo=UTC).timestamp())

    surface.update("start_impact_time", instant=instant)

    assert surface.stored().impact_started_at == datetime(2026, 10, 1, 13, 30, tzinfo=UTC)
    [notice] = surface.posts()
    assert notice.startswith(f"<@{USER_ID}> has updated the field start_impact_time to <!date^{instant}^")
    assert "|2026-10-01T13:30:00+00:00>" in notice


def test_flipping_the_security_flag_writes_it_and_announces_it_with_no_other_action(surface: _Surface) -> None:
    surface.update("security_incident", option="yes")

    assert surface.stored().security_incident is True
    assert surface.posts() == (
        f"<@{USER_ID}> has updated the field security_incident to Yes\n<@{USER_ID}> a mis à jour le champ security_incident à Oui",
    )
    assert surface.private_lines() == []


def test_submitting_a_status_moves_the_record_the_report_line_the_list_and_tells_the_channel(surface: _Surface) -> None:
    surface.update("status", option="Ready to be Reviewed")

    assert surface.stored().status is IncidentStatus.READY_TO_BE_REVIEWED
    assert surface.reports.status_text_of(REPORT) is IncidentStatus.READY_TO_BE_REVIEWED
    [row] = surface.projection.rows
    assert row[3] == "Ready to be Reviewed"
    assert surface.posts()[0].startswith(f"<@{USER_ID}> has updated the field status to Ready to be Reviewed\n")


def test_a_status_whose_list_write_fails_tells_the_submitter_and_still_tells_the_channel(surface: _Surface) -> None:
    surface.projection = InMemoryIncidentListProjection(
        fail_with=OperationResult.permanent_error("no sheet", ErrorCode.CONFIG_NOT_CONFIGURED)
    )

    surface.update("status", option="Reviewed")

    assert surface.private_lines() == ["Couldn't update the status in the incident list."]
    assert len(surface.posts()) == 1


def test_an_archived_channel_keeps_the_change_and_tells_the_submitter_nothing_was_posted(surface: _Surface) -> None:
    surface.show()
    surface.press("severity")
    surface.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, archived_ids=[CHANNEL_ID])

    surface.submit(surface.pushed(), option="sev-3")

    assert surface.stored().severity is Severity.SEV3
    assert surface.private_lines() == [
        "The incident channel can't be written to, so the change was saved but nothing was posted there."
    ]


def test_a_failed_record_write_is_told_privately_and_nothing_else_happens(surface: _Surface) -> None:
    surface.show()
    surface.press("severity")
    surface.records.go_down()

    surface.submit(surface.pushed(), option="sev-1")

    assert surface.private_lines() == ["The incidents database is temporarily unavailable. Please try again later."]
    assert surface.posts() == ()
    assert surface.reply.calls_to("update_view") == []


def test_a_modal_opened_in_french_answers_its_submitter_in_french(surface: _Surface) -> None:
    surface.show(locale="fr-FR")
    surface.press("severity")
    surface.records.go_down()

    surface.submit(surface.pushed(), option="sev-1")

    assert surface.private_lines() == [
        "La base de données des incidents est temporairement indisponible. Veuillez réessayer plus tard."
    ]


def test_a_refresh_of_a_closed_modal_is_not_reported_as_a_failed_update(monkeypatch: pytest.MonkeyPatch) -> None:
    class ClosedRoot(FakeSlackReply):
        def update_view(self, *, view_id: str, view: dict[str, Any], hash: str | None = None) -> OperationResult[None]:  # noqa: A002 -- Slack's parameter name
            super().update_view(view_id=view_id, view=view, hash=hash)
            return OperationResult.permanent_error("view gone", error_code="not_found")

    surface = _Surface(monkeypatch, ClosedRoot())

    surface.update("severity", option="sev-4")

    assert surface.stored().severity is Severity.SEV4
    assert surface.private_lines() == []


def test_a_submission_without_a_readable_value_writes_nothing(surface: _Surface) -> None:
    surface.show()
    surface.press("severity")

    assert surface.submit(surface.pushed()) == ["ack"]

    assert surface.stored().severity is Severity.SEV2
    assert surface.posts() == ()
