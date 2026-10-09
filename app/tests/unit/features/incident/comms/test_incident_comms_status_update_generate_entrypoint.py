"""Tests for the Draft with AI button listener of the review form.

The listener acks, reads the instructions, the security checkbox and the
responder's current form values from the action's view state, and fills the
pending draft through ``generate_status_update_draft``. A fill shows the new
draft's form with a notice; a refusal or failure re-renders the typed values
with a notice and the instructions kept; a stale draft shows the conflict view.
While the model runs the modal shows the generating view. Every outcome is a
``views_update`` of the pressed modal; nothing is posted to a channel.

Most tests stub the service boundary with recording fakes in the entrypoint
module's namespace (``generate_status_update_draft`` and
``get_draft_for_review``) that return real ``OperationResult`` values. The
generate fake calls the listener's ``on_started`` callback as many times as the
stubbed outcome made model calls, so the generating state is driven exactly as
the service drives it. Every fake writes to one shared event log with the ack
and the client, so call order is asserted directly. Expected views come from
the platform view builders, and notice wording is pinned literally (the
catalogue is not loaded in unit tests).

``TestWithTheService`` binds the real services to a core
``InMemoryStatusUpdateStore`` and stubs for the lookup, the transcript reader,
the security flag reader and a recording text generator, so the number of model
calls and what reaches the model are asserted at the listener.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.comms import form
from features.incident.comms.approval import get_draft_for_review
from features.incident.comms.domain import (
    NoNewInformationWording,
    StatusUpdateDraftOutcome,
    StatusUpdateEdit,
    StatusUpdateOutcomeKind,
)
from features.incident.comms.entrypoints.slack import (
    handle_generate_action,
    handle_history_action,
    handle_new_update_action,
    handle_open_action,
    handle_published_action,
    handle_review_action,
    handle_review_submission,
    handle_save_action,
    register,
)
from features.incident.comms.entrypoints.slack_views import (
    GENERATE_ACTION_ID,
    HISTORY_ACTION_ID,
    NEW_ACTION_ID,
    OPEN_ACTION_ID,
    PUBLISHED_ACTION_ID,
    REVIEW_ACTION_ID,
    REVIEW_CALLBACK_ID,
    SAVE_ACTION_ID,
    build_generating_view,
    build_no_new_information_wording,
    build_review_error_view,
    build_review_view,
)
from features.incident.comms.service import DRAFT_UNPARSEABLE_CODE, generate_status_update_draft
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import (
    IncidentSecurityFlag,
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_USER = "U0FILLER"
_SEQUENCE = 3
_VIEW_ID = "VREVIEW"
_VIEW_HASH = "review-hash=="
_NEXT_HASH = "next-hash=="
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_GUIDANCE = "do not name the vendor"
_FIELDS = ("affected_service", "impact", "current_action", "workaround")

_NOTICES = {
    "en-US": {
        "generated_note": "Drafted with AI. Review the new draft before you approve it.",
        "generate_carried_forward": "Nothing new since the last approved update, so the current action now says there "
        "is no new information.",
        "generate_failed": "Couldn't draft with AI right now, so your text was kept. Please try again shortly.",
        "generate_unparseable": "I couldn't turn the model's answer into a status update, so your text was kept. "
        "Please try again.",
        "generate_security": "This incident is, or may be, a security incident. Drafting with AI sends the incident "
        "channel and comms content to the AI model. To continue, check the box below, then press Draft with AI.",
        "generate_unavailable": "AI drafting isn't available right now, so your text was kept. Write the update in the "
        "fields below.",
        "generate_empty_history": "There's no conversation from people to draft from yet, so your text was kept.",
    },
    "fr-FR": {
        "generated_note": "Brouillon rédigé avec l'IA. Révisez-le avant de l'approuver.",
        "generate_carried_forward": "Rien de nouveau depuis la dernière mise à jour approuvée; la mesure en cours "
        "indique maintenant qu'il n'y a aucune nouvelle information.",
        "generate_failed": "Impossible de rédiger avec l'IA pour le moment; votre texte a été conservé. "
        "Veuillez réessayer sous peu.",
        "generate_unparseable": "Je n'ai pas pu transformer la réponse du modèle en mise à jour de statut; votre texte "
        "a été conservé. Veuillez réessayer.",
        "generate_security": "Cet incident est, ou pourrait être, un incident de sécurité. La rédaction avec l'IA "
        "envoie le contenu du canal de l'incident et des communications au modèle d'IA. Pour continuer, cochez la "
        "case ci-dessous, puis appuyez sur Rédiger avec l'IA.",
        "generate_unavailable": "La rédaction par IA n'est pas disponible pour le moment; votre texte a été conservé. "
        "Rédigez la mise à jour dans les champs ci-dessous.",
        "generate_empty_history": "Il n'y a pas encore de conversation à partir de laquelle rédiger; votre texte a été conservé.",
    },
}


def _text(language: str, prefix: str = "") -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{prefix}{language} service",
        impact=f"{prefix}{language} impact",
        current_action=f"{prefix}{language} action",
        workaround=f"{prefix}{language} workaround",
    )


_DRAFT = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=_SEQUENCE,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.IDENTIFIED,
    en=_text("en"),
    fr=_text("fr"),
    next_update_at=_NOW,
    author="U999",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc123",
    created_at=_NOW,
)
_EDIT = StatusUpdateEdit(stage=StatusUpdateStage.MONITORING, en=_text("en", "edited "), fr=_text("fr", "edited "))
_EDITED_DRAFT = replace(_DRAFT, stage=_EDIT.stage, en=_EDIT.en, fr=_EDIT.fr)
_STORED_EDIT = StatusUpdateEdit(stage=_DRAFT.stage, en=_DRAFT.en, fr=_DRAFT.fr)
_FILLED = replace(
    _DRAFT,
    sequence=_SEQUENCE + 1,
    stage=StatusUpdateStage.MONITORING,
    en=_text("en", "filled "),
    fr=_text("fr", "filled "),
    author=_USER,
)


@dataclass
class _Services:
    """Recording fakes for the generate service and the review read.

    ``model_calls`` is how many times the generate fake reports a model call
    starting through ``on_started``: one for outcomes produced after the model
    answered, zero for refusals made before it and for a carry forward.
    """

    events: list[str]
    generate_result: OperationResult[StatusUpdateDraftOutcome] = field(
        default_factory=lambda: OperationResult.success(
            data=StatusUpdateDraftOutcome(update=_FILLED, kind=StatusUpdateOutcomeKind.DRAFTED)
        )
    )
    review_result: OperationResult[StatusUpdate] = field(default_factory=lambda: OperationResult.success(data=_DRAFT))
    model_calls: int = 1
    generate_calls: list[dict[str, Any]] = field(default_factory=list)
    review_calls: list[tuple[str, int]] = field(default_factory=list)

    async def generate_status_update_draft(
        self,
        conversation_id: str,
        sequence: int,
        *,
        current: StatusUpdateEdit,
        author: str,
        wording: NoNewInformationWording,
        instructions: str = "",
        security_confirmed: bool = False,
        on_started: Any = None,
    ) -> OperationResult[StatusUpdateDraftOutcome]:
        self.events.append("generate_status_update_draft")
        self.generate_calls.append(
            {
                "conversation_id": conversation_id,
                "sequence": sequence,
                "current": current,
                "author": author,
                "wording": wording,
                "instructions": instructions,
                "security_confirmed": security_confirmed,
            }
        )
        for _ in range(self.model_calls):
            on_started()
        return self.generate_result

    async def get_draft_for_review(self, incident_id: str, sequence: int) -> OperationResult[StatusUpdate]:
        self.events.append("get_draft_for_review")
        self.review_calls.append((incident_id, sequence))
        return self.review_result


@pytest.fixture
def events() -> list[str]:
    return []


@pytest.fixture
def services(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> _Services:
    fakes = _Services(events=events)
    monkeypatch.setattr(form, "generate_status_update_draft", fakes.generate_status_update_draft)
    monkeypatch.setattr(form, "get_draft_for_review", fakes.get_draft_for_review)
    return fakes


@pytest.fixture
def ack(events: list[str]) -> MagicMock:
    return MagicMock(side_effect=lambda *args, **kwargs: events.append("ack"))


@pytest.fixture
def client(events: list[str]) -> MagicMock:
    slack_client = MagicMock()

    def views_update(**kwargs: Any) -> dict[str, Any]:
        events.append("views_update")
        return {"ok": True, "view": {"hash": _NEXT_HASH}}

    slack_client.views_update.side_effect = views_update
    return slack_client


def _review_metadata(locale: str = "en-US", sequence: int = _SEQUENCE) -> str:
    return json.dumps({"channel_id": _CHANNEL, "locale": locale, "incident_id": _INCIDENT, "sequence": sequence})


def _generate_body(
    instructions: str | None = _GUIDANCE,
    *,
    locale: str = "en-US",
    edit: StatusUpdateEdit = _EDIT,
    stage_value: str | None = None,
    extra_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A block_actions body for Draft with AI pressed in the review form, its fields filled from ``edit``."""
    values: dict[str, Any] = {
        f"{language}.{name}": {"text": {"type": "plain_text_input", "value": getattr(text, name)}}
        for language, text in (("en", edit.en), ("fr", edit.fr))
        for name in _FIELDS
    }
    stage = stage_value or edit.stage.value
    values["stage"] = {
        "stage": {"type": "static_select", "selected_option": {"text": {"type": "plain_text", "text": stage}, "value": stage}}
    }
    values["instructions"] = {"text": {"type": "plain_text_input", "value": instructions}}
    values |= extra_values or {}
    return {
        "type": "block_actions",
        "user": {"id": _USER},
        "trigger_id": "trigger-123",
        "view": {
            "id": _VIEW_ID,
            "hash": _VIEW_HASH,
            "type": "modal",
            "callback_id": REVIEW_CALLBACK_ID,
            "private_metadata": _review_metadata(locale),
            "state": {"values": values},
        },
        "actions": [{"action_id": GENERATE_ACTION_ID, "block_id": "generate_button", "type": "button"}],
    }


def _checkbox(*selected: str) -> dict[str, Any]:
    """The security confirmation checkbox's state with ``selected`` option values."""
    options = [{"text": {"type": "plain_text", "text": "confirm"}, "value": value} for value in selected]
    return {"security_confirm": {"confirm": {"type": "checkboxes", "selected_options": options}}}


def _generate_call(
    *, current: StatusUpdateEdit = _EDIT, instructions: str = _GUIDANCE, security_confirmed: bool = False
) -> dict[str, Any]:
    return {
        "conversation_id": _CHANNEL,
        "sequence": _SEQUENCE,
        "current": current,
        "author": _USER,
        "wording": build_no_new_information_wording(),
        "instructions": instructions,
        "security_confirmed": security_confirmed,
    }


def _client_method_names(client: MagicMock) -> list[str]:
    return [method_call[0] for method_call in client.method_calls]


class TestRegister:
    def test_registers_exactly_the_final_listeners(self) -> None:
        """Seven block actions and the approval submission; no overview Draft, Confirm and draft or Redraft."""
        registrar = FakeSlackRegistrar()

        register(registrar)

        assert registrar.block_actions == {
            NEW_ACTION_ID: handle_new_update_action,
            SAVE_ACTION_ID: handle_save_action,
            GENERATE_ACTION_ID: handle_generate_action,
            REVIEW_ACTION_ID: handle_review_action,
            OPEN_ACTION_ID: handle_open_action,
            HISTORY_ACTION_ID: handle_history_action,
            PUBLISHED_ACTION_ID: handle_published_action,
        }
        assert registrar.view_submissions == {REVIEW_CALLBACK_ID: handle_review_submission}


class TestDrafted:
    def test_acks_first_then_fills_with_the_form_values_as_the_base(
        self, ack: MagicMock, client: MagicMock, services: _Services, events: list[str]
    ) -> None:
        """The service gets the conversation, the sequence, the typed values, the wording, the instructions and the presser."""
        handle_generate_action(ack, _generate_body(), client)

        ack.assert_called_once_with()
        assert services.generate_calls == [_generate_call()]
        assert events == ["ack", "generate_status_update_draft", "views_update", "views_update"]

    @pytest.mark.parametrize("instructions", ["", "   ", None], ids=["empty", "spaces", "null"])
    def test_blank_instructions_still_draft_from_the_conversation(
        self, ack: MagicMock, client: MagicMock, services: _Services, instructions: str | None
    ) -> None:
        """Instructions are optional: blank ones reach the service as typed, which drafts from the conversation."""
        handle_generate_action(ack, _generate_body(instructions), client)

        assert services.generate_calls == [_generate_call(instructions=instructions or "")]
        assert services.review_calls == []

    def test_an_unreadable_stage_fills_from_the_stored_draft(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """When the stage cannot be parsed the stored draft is the model's base."""
        handle_generate_action(ack, _generate_body(stage_value="not-a-stage"), client)

        assert services.review_calls == [(_INCIDENT, _SEQUENCE)]
        assert services.generate_calls == [_generate_call(current=_STORED_EDIT)]

    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_shows_generating_then_the_form_of_the_new_draft(
        self, ack: MagicMock, client: MagicMock, services: _Services, locale: str
    ) -> None:
        """The modal shows the generating view, then the new draft's form with the new sequence, a note and no instructions."""
        handle_generate_action(ack, _generate_body(locale=locale), client)

        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_generating_view(locale, _review_metadata(locale))),
            call(
                view_id=_VIEW_ID,
                hash=_NEXT_HASH,
                view=build_review_view(
                    _FILLED,
                    locale,
                    _review_metadata(locale, sequence=_SEQUENCE + 1),
                    notice=_NOTICES[locale]["generated_note"],
                ),
            ),
        ]

    def test_only_updates_the_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """The only Slack calls are views_update: nothing is posted to the incident channel."""
        handle_generate_action(ack, _generate_body(), client)

        assert _client_method_names(client) == ["views_update", "views_update"]

    def test_slack_failures_are_not_raised(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A views.update exception never escapes the listener; the fill still ran once."""
        client.views_update.side_effect = RuntimeError("view_not_found")

        handle_generate_action(ack, _generate_body(), client)

        assert services.generate_calls == [_generate_call()]


class TestCarriedForward:
    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_nothing_new_shows_the_carried_draft_with_a_notice_and_no_generating_view(
        self, ack: MagicMock, client: MagicMock, services: _Services, locale: str
    ) -> None:
        """No model call was made, so the modal goes straight to the new draft's form with the nothing-new notice."""
        carried = replace(_FILLED, en=replace(_EDIT.en, current_action="No new information."))
        services.model_calls = 0
        services.generate_result = OperationResult.success(
            data=StatusUpdateDraftOutcome(update=carried, kind=StatusUpdateOutcomeKind.CARRIED_FORWARD)
        )

        handle_generate_action(ack, _generate_body("", locale=locale), client)

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_review_view(
                    carried,
                    locale,
                    _review_metadata(locale, sequence=carried.sequence),
                    notice=_NOTICES[locale]["generate_carried_forward"],
                ),
            )
        ]


class TestFailureKeepsTheTypedValues:
    @pytest.mark.parametrize(
        ("result", "notice_key"),
        [
            (OperationResult.transient_error(message="rate limited", error_code=ErrorCode.RATE_LIMITED), "generate_failed"),
            (
                OperationResult.permanent_error(message="unreadable", error_code=DRAFT_UNPARSEABLE_CODE),
                "generate_unparseable",
            ),
            (
                OperationResult.transient_error(message="store down", error_code=ErrorCode.STATUS_UPDATE_UNREADABLE),
                "generate_failed",
            ),
        ],
        ids=["model-failure", "unparseable", "store-error"],
    )
    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_the_form_comes_back_with_the_edits_the_instructions_and_a_localized_notice(
        self,
        ack: MagicMock,
        client: MagicMock,
        services: _Services,
        result: OperationResult[StatusUpdateDraftOutcome],
        notice_key: str,
        locale: str,
    ) -> None:
        """After the generating view, the form is re-rendered from the responder's values with their instructions kept."""
        services.generate_result = result

        handle_generate_action(ack, _generate_body(locale=locale), client)

        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_generating_view(locale, _review_metadata(locale))),
            call(
                view_id=_VIEW_ID,
                hash=_NEXT_HASH,
                view=build_review_view(
                    _EDITED_DRAFT,
                    locale,
                    _review_metadata(locale),
                    notice=_NOTICES[locale][notice_key],
                    instructions=_GUIDANCE,
                ),
            ),
        ]

    def test_empty_history_keeps_the_typed_values_with_its_own_notice(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """A first update with nobody's message to draft from is refused before the model; the form says why."""
        services.model_calls = 0
        services.generate_result = OperationResult.permanent_error(message="empty", error_code=ErrorCode.EMPTY_HISTORY)

        handle_generate_action(ack, _generate_body(""), client)

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_review_view(
                    _EDITED_DRAFT, "en-US", _review_metadata(), notice=_NOTICES["en-US"]["generate_empty_history"]
                ),
            )
        ]

    def test_unavailable_text_generation_keeps_the_typed_values_without_the_ai_section(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """With the generator gone the form says AI drafting is unavailable and stops offering it."""
        services.generate_result = OperationResult.permanent_error(
            message="off", error_code=ErrorCode.TEXT_GENERATION_UNAVAILABLE
        )

        handle_generate_action(ack, _generate_body(), client)

        assert client.views_update.call_args_list[-1] == call(
            view_id=_VIEW_ID,
            hash=_NEXT_HASH,
            view=build_review_view(
                _EDITED_DRAFT,
                "en-US",
                _review_metadata(),
                notice=_NOTICES["en-US"]["generate_unavailable"],
                instructions=_GUIDANCE,
                with_ai=False,
            ),
        )

    def test_only_updates_the_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A failed fill posts nothing either."""
        services.generate_result = OperationResult.permanent_error(message="unreadable", error_code=DRAFT_UNPARSEABLE_CODE)

        handle_generate_action(ack, _generate_body(), client)

        assert _client_method_names(client) == ["views_update", "views_update"]

    def test_a_failed_read_with_an_unreadable_stage_shows_the_error_view(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """Without typed values or the stored draft there is no base and nothing to re-render, so nothing is filled."""
        services.review_result = OperationResult.transient_error(message="down", error_code=ErrorCode.STATUS_UPDATE_UNREADABLE)

        handle_generate_action(ack, _generate_body(stage_value="not-a-stage"), client)

        assert services.generate_calls == []
        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_review_error_view(ErrorCode.STATUS_UPDATE_UNREADABLE, "en-US", _review_metadata()),
            )
        ]


class TestSecurityConfirmation:
    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_a_refusal_rerenders_the_form_with_the_warning_and_the_checkbox(
        self, ack: MagicMock, client: MagicMock, services: _Services, locale: str
    ) -> None:
        """No model call was made, so there is no generating view: the form comes back with the warning, checkbox and instructions."""
        services.model_calls = 0
        services.generate_result = OperationResult.permanent_error(
            message="confirm", error_code=ErrorCode.SECURITY_CONFIRMATION_REQUIRED
        )

        handle_generate_action(ack, _generate_body(locale=locale), client)

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_review_view(
                    _EDITED_DRAFT,
                    locale,
                    _review_metadata(locale),
                    notice=_NOTICES[locale]["generate_security"],
                    instructions=_GUIDANCE,
                    security_confirm=True,
                ),
            )
        ]
        assert _client_method_names(client) == ["views_update"]

    def test_pressing_draft_with_ai_with_the_box_checked_passes_the_confirmation(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """The checked confirmation reaches the service as ``security_confirmed=True``."""
        handle_generate_action(ack, _generate_body(extra_values=_checkbox("confirmed")), client)

        assert services.generate_calls == [_generate_call(security_confirmed=True)]

    def test_an_unchecked_box_does_not_confirm(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """Showing the checkbox is not consent; left unchecked it passes ``security_confirmed=False``."""
        handle_generate_action(ack, _generate_body(extra_values=_checkbox()), client)

        assert services.generate_calls == [_generate_call(security_confirmed=False)]


class TestConflict:
    def test_an_append_conflict_shows_the_review_conflict_view(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """Another writer took the next sequence after the model answered: the modal says the draft changed elsewhere."""
        services.generate_result = OperationResult.permanent_error(
            message="conflict", error_code=ErrorCode.STATUS_UPDATE_CONFLICT
        )

        handle_generate_action(ack, _generate_body(), client)

        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_generating_view("en-US", _review_metadata())),
            call(
                view_id=_VIEW_ID,
                hash=_NEXT_HASH,
                view=build_review_error_view(ErrorCode.STATUS_UPDATE_CONFLICT, "en-US", _review_metadata()),
            ),
        ]

    def test_a_stale_draft_shows_the_review_conflict_view_without_generating_state(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """A draft that changed before the model was called shows the conflict view alone."""
        services.model_calls = 0
        services.generate_result = OperationResult.permanent_error(
            message="conflict", error_code=ErrorCode.STATUS_UPDATE_CONFLICT
        )

        handle_generate_action(ack, _generate_body(locale="fr-FR"), client)

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_review_error_view(ErrorCode.STATUS_UPDATE_CONFLICT, "fr-FR", _review_metadata("fr-FR")),
            )
        ]


def _at(minutes: int) -> datetime:
    return _NOW - timedelta(minutes=minutes)


_APPROVED = replace(_DRAFT, sequence=_SEQUENCE - 1, state=StatusUpdateState.APPROVED, transcript_cutoff=_at(60))
_PENDING = replace(_DRAFT, transcript_cutoff=_at(60))


def _model_answer() -> str:
    answer = {"stage": "monitoring"} | {f"{lang}_{name}": f"{lang} {name} filled" for lang in ("en", "fr") for name in _FIELDS}
    return json.dumps(answer)


class _StubLookup:
    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        return OperationResult.success(data=_INCIDENT)


class _StubReader:
    def __init__(self, messages: Sequence[TranscriptMessage]) -> None:
        self._messages = list(messages)

    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        return _at(600)

    def read_transcript(
        self, conversation_id: str, *, since: datetime, limit: int, exclude_own_and_system_messages: bool = False
    ) -> Sequence[TranscriptMessage]:
        return self._messages


class _StubSecurityReader:
    def __init__(self, flag: IncidentSecurityFlag) -> None:
        self._flag = flag
        self.calls: list[str] = []

    def read_security_flag(self, incident_id: str) -> OperationResult[IncidentSecurityFlag]:
        self.calls.append(incident_id)
        return OperationResult.success(data=self._flag)


class _RecordingGenerator:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def summarize(
        self, transcript: str, *, instructions: str | None = None, max_output_tokens: int | None = None
    ) -> OperationResult[str]:
        self.calls.append({"transcript": transcript, "instructions": instructions})
        return OperationResult.success(data=_model_answer())


@dataclass
class _World:
    store: InMemoryStatusUpdateStore
    generator: _RecordingGenerator
    security_reader: _StubSecurityReader


def _bind(monkeypatch: pytest.MonkeyPatch, *, messages: Sequence[TranscriptMessage], flag: IncidentSecurityFlag) -> _World:
    """Bind the real service to an in-memory store holding an approved update and the pending draft."""
    world = _World(InMemoryStatusUpdateStore(), _RecordingGenerator(), _StubSecurityReader(flag))
    world.store.append(_APPROVED)
    world.store.append(_PENDING)
    service = partial(
        generate_status_update_draft,
        lookup=_StubLookup(),
        reader=_StubReader(messages),
        store=world.store,
        generator=world.generator,
        security_reader=world.security_reader,
        now=_NOW,
    )
    monkeypatch.setattr(form, "generate_status_update_draft", service)
    monkeypatch.setattr(form, "get_draft_for_review", partial(get_draft_for_review, store=world.store))
    return world


def _latest(world: _World) -> StatusUpdate:
    latest = world.store.latest(_INCIDENT).data
    assert latest is not None
    return latest


_OLD = TranscriptMessage(author="Ada", text="seeing 500s", posted_at=_at(90))
_NEW = TranscriptMessage(author="Ada", text="rolled back", posted_at=_at(5))


class TestWithTheService:
    def test_no_new_messages_makes_no_model_call_and_shows_the_carried_wording(
        self, monkeypatch: pytest.MonkeyPatch, client: MagicMock
    ) -> None:
        """Code decides nothing is new: zero model calls, and the new draft's current action is the no-new-information wording."""
        world = _bind(monkeypatch, messages=[_OLD], flag=IncidentSecurityFlag.YES)

        handle_generate_action(MagicMock(), _generate_body(""), client)

        assert world.generator.calls == [] and world.security_reader.calls == []
        carried = _latest(world)
        assert (carried.sequence, carried.en.current_action) == (_SEQUENCE + 1, build_no_new_information_wording().en)
        (sent,) = client.views_update.call_args_list
        assert sent.kwargs["view"]["blocks"][0]["text"]["text"] == _NOTICES["en-US"]["generate_carried_forward"]
        client.chat_postMessage.assert_not_called()

    def test_new_messages_make_one_model_call_and_show_the_new_draft(
        self, monkeypatch: pytest.MonkeyPatch, client: MagicMock
    ) -> None:
        """Someone posted since the approved update, so the model is called once and its fields are the new draft."""
        world = _bind(monkeypatch, messages=[_NEW], flag=IncidentSecurityFlag.NO)

        handle_generate_action(MagicMock(), _generate_body(""), client)

        assert len(world.generator.calls) == 1
        filled = _latest(world)
        assert (filled.sequence, filled.en.impact) == (_SEQUENCE + 1, "en impact filled")
        assert json.loads(client.views_update.call_args_list[-1].kwargs["view"]["private_metadata"])["sequence"] == (
            _SEQUENCE + 1
        )
        client.chat_postMessage.assert_not_called()

    def test_typed_instructions_reach_the_model(self, monkeypatch: pytest.MonkeyPatch, client: MagicMock) -> None:
        """The responder's guidance is part of the one model call's instructions, even with nothing new."""
        world = _bind(monkeypatch, messages=[_OLD], flag=IncidentSecurityFlag.NO)

        handle_generate_action(MagicMock(), _generate_body(_GUIDANCE), client)

        (model_call,) = world.generator.calls
        assert _GUIDANCE in str(model_call["instructions"])

    def test_a_security_incident_makes_no_model_call_until_the_box_is_checked(
        self, monkeypatch: pytest.MonkeyPatch, client: MagicMock
    ) -> None:
        """Unconfirmed: no model call and the checkbox is shown. Checked: one call, and the flag is not read again."""
        world = _bind(monkeypatch, messages=[_NEW], flag=IncidentSecurityFlag.YES)

        handle_generate_action(MagicMock(), _generate_body(), client)

        assert world.generator.calls == []
        assert _latest(world) == _PENDING
        refused = client.views_update.call_args_list[-1].kwargs["view"]
        assert "security_confirm" in [block.get("block_id") for block in refused["blocks"]]

        reads_before = len(world.security_reader.calls)
        handle_generate_action(MagicMock(), _generate_body(extra_values=_checkbox("confirmed")), client)

        assert len(world.generator.calls) == 1
        assert len(world.security_reader.calls) == reads_before
        client.chat_postMessage.assert_not_called()
