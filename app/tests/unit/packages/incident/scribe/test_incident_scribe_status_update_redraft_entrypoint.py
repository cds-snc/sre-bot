"""Tests for the Redraft button listener of the review modal.

The listener acks, reads the instructions, the security checkbox and the
reviewer's current form values from the action's view state, and either
re-renders the form with a notice (blank instructions, a refusal, a failure)
or redrafts through the service and shows the review form of the new draft.
While the model runs the modal shows the redrafting view. Every outcome is a
``views_update`` of the pressed modal; nothing is posted to a channel.

The service boundary is stubbed with recording fakes in the entrypoint
module's namespace (``redraft_status_update`` and ``get_draft_for_review``)
that return real ``OperationResult`` values. The redraft fake calls the
listener's ``on_started`` callback as many times as the stubbed outcome made
model calls, so the redrafting state is driven exactly as the service drives
it. Every fake writes to one shared event log with the ack and the client, so
call order is asserted directly. Expected views come from the platform view
builders, and notice wording is pinned literally (the catalogue is not loaded
in unit tests), so each assertion compares the exact views sent in order.
"""

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.domain import StatusUpdateEdit
from packages.incident.scribe.entrypoints import slack as slack_entrypoints
from packages.incident.scribe.entrypoints.slack import (
    handle_draft_action,
    handle_draft_confirmed_action,
    handle_history_action,
    handle_new_update_action,
    handle_open_action,
    handle_published_action,
    handle_redraft_action,
    handle_review_action,
    handle_review_submission,
    handle_save_action,
    register,
)
from packages.incident.scribe.entrypoints.slack_views import (
    CONFIRM_ACTION_ID,
    DRAFT_ACTION_ID,
    HISTORY_ACTION_ID,
    NEW_ACTION_ID,
    OPEN_ACTION_ID,
    PUBLISHED_ACTION_ID,
    REDRAFT_ACTION_ID,
    REVIEW_ACTION_ID,
    REVIEW_CALLBACK_ID,
    SAVE_ACTION_ID,
    build_redrafting_view,
    build_review_error_view,
    build_review_view,
)
from packages.incident.scribe.status_update import DRAFT_UNPARSEABLE_CODE
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_USER = "U0REDRAFTER"
_SEQUENCE = 3
_VIEW_ID = "VREVIEW"
_VIEW_HASH = "review-hash=="
_NEXT_HASH = "next-hash=="
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_GUIDANCE = "do not name the vendor"
_FIELDS = ("affected_service", "impact", "current_action", "workaround")

_NOTICES = {
    "en-US": {
        "redrafted_note": "Redrafted from your instructions. Review the new draft before you approve it.",
        "redraft_blank": "Enter instructions for the new draft, then press Redraft.",
        "redraft_failed": "Couldn't redraft the status update right now, so the previous draft was kept. "
        "Please try again shortly.",
        "redraft_unparseable": "I couldn't turn the model's answer into a status update, so the previous draft was kept. "
        "Please try again.",
        "redraft_security": "This incident is, or may be, a security incident. Redrafting sends the incident channel and "
        "comms content to the AI model. To continue, check the box below, then press Redraft.",
    },
    "fr-FR": {
        "redrafted_note": "Nouveau brouillon rédigé selon vos instructions. Révisez-le avant de l'approuver.",
        "redraft_blank": "Entrez des instructions pour le nouveau brouillon, puis appuyez sur Rédiger à nouveau.",
        "redraft_failed": "Impossible de rédiger à nouveau la mise à jour de statut pour le moment; le brouillon "
        "précédent a été conservé. Veuillez réessayer sous peu.",
        "redraft_unparseable": "Je n'ai pas pu transformer la réponse du modèle en mise à jour de statut; le brouillon "
        "précédent a été conservé. Veuillez réessayer.",
        "redraft_security": "Cet incident est, ou pourrait être, un incident de sécurité. La nouvelle rédaction envoie le "
        "contenu du canal de l'incident et des communications au modèle d'IA. Pour continuer, cochez la case "
        "ci-dessous, puis appuyez sur Rédiger à nouveau.",
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
_REDRAFTED = replace(
    _DRAFT,
    sequence=_SEQUENCE + 1,
    stage=StatusUpdateStage.MONITORING,
    en=_text("en", "redrafted "),
    fr=_text("fr", "redrafted "),
    author=_USER,
)


@dataclass
class _Services:
    """Recording fakes for the redraft service and the review read.

    ``model_calls`` is how many times the redraft fake reports a model call
    starting through ``on_started``: one for outcomes produced after the model
    answered, zero for refusals made before it.
    """

    events: list[str]
    redraft_result: OperationResult[StatusUpdate] = field(default_factory=lambda: OperationResult.success(data=_REDRAFTED))
    review_result: OperationResult[StatusUpdate] = field(default_factory=lambda: OperationResult.success(data=_DRAFT))
    model_calls: int = 1
    redraft_calls: list[dict[str, Any]] = field(default_factory=list)
    review_calls: list[tuple[str, int]] = field(default_factory=list)

    async def redraft_status_update(
        self,
        conversation_id: str,
        sequence: int,
        *,
        instructions: str,
        current: StatusUpdateEdit,
        author: str,
        security_confirmed: bool = False,
        on_started: Any = None,
    ) -> OperationResult[StatusUpdate]:
        self.events.append("redraft_status_update")
        self.redraft_calls.append(
            {
                "conversation_id": conversation_id,
                "sequence": sequence,
                "instructions": instructions,
                "current": current,
                "author": author,
                "security_confirmed": security_confirmed,
            }
        )
        for _ in range(self.model_calls):
            on_started()
        return self.redraft_result

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
    monkeypatch.setattr(slack_entrypoints, "redraft_status_update", fakes.redraft_status_update)
    monkeypatch.setattr(slack_entrypoints, "get_draft_for_review", fakes.get_draft_for_review)
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


def _redraft_body(
    instructions: str | None = _GUIDANCE,
    *,
    locale: str = "en-US",
    stage_value: str = _EDIT.stage.value,
    extra_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A block_actions body for Redraft pressed in the review modal, its form filled from ``_EDIT``."""
    values: dict[str, Any] = {
        f"{language}.{name}": {"text": {"type": "plain_text_input", "value": getattr(text, name)}}
        for language, text in (("en", _EDIT.en), ("fr", _EDIT.fr))
        for name in _FIELDS
    }
    values["stage"] = {
        "stage": {
            "type": "static_select",
            "selected_option": {"text": {"type": "plain_text", "text": stage_value}, "value": stage_value},
        }
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
        "actions": [{"action_id": REDRAFT_ACTION_ID, "block_id": "redraft_button", "type": "button"}],
    }


def _checkbox(*selected: str) -> dict[str, Any]:
    """The security confirmation checkbox's state with ``selected`` option values."""
    options = [{"text": {"type": "plain_text", "text": "confirm"}, "value": value} for value in selected]
    return {"security_confirm": {"confirm": {"type": "checkboxes", "selected_options": options}}}


def _redraft_call(*, current: StatusUpdateEdit = _EDIT, security_confirmed: bool = False) -> dict[str, Any]:
    return {
        "conversation_id": _CHANNEL,
        "sequence": _SEQUENCE,
        "instructions": _GUIDANCE,
        "current": current,
        "author": _USER,
        "security_confirmed": security_confirmed,
    }


def _client_method_names(client: MagicMock) -> list[str]:
    return [method_call[0] for method_call in client.method_calls]


class TestRegister:
    def test_registers_redraft_beside_the_existing_listeners(self) -> None:
        """Registration adds the Redraft block action and keeps every existing listener."""
        registrar = FakeSlackRegistrar()

        register(registrar)

        assert registrar.block_actions == {
            DRAFT_ACTION_ID: handle_draft_action,
            CONFIRM_ACTION_ID: handle_draft_confirmed_action,
            NEW_ACTION_ID: handle_new_update_action,
            REVIEW_ACTION_ID: handle_review_action,
            OPEN_ACTION_ID: handle_open_action,
            HISTORY_ACTION_ID: handle_history_action,
            PUBLISHED_ACTION_ID: handle_published_action,
            REDRAFT_ACTION_ID: handle_redraft_action,
            SAVE_ACTION_ID: handle_save_action,
        }
        assert registrar.view_submissions == {REVIEW_CALLBACK_ID: handle_review_submission}


class TestBlankInstructions:
    @pytest.mark.parametrize("instructions", ["", "   ", "\n \t", None], ids=["empty", "spaces", "whitespace", "null"])
    def test_blank_instructions_rerender_the_form_with_a_notice_and_never_redraft(
        self, ack: MagicMock, client: MagicMock, services: _Services, events: list[str], instructions: str | None
    ) -> None:
        """The form comes back with the reviewer's edits and the blank notice; the service is never awaited."""
        handle_redraft_action(ack, _redraft_body(instructions), client)

        assert services.redraft_calls == []
        assert services.review_calls == [(_INCIDENT, _SEQUENCE)]
        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_review_view(_EDITED_DRAFT, "en-US", _review_metadata(), notice=_NOTICES["en-US"]["redraft_blank"]),
            )
        ]
        assert events == ["ack", "get_draft_for_review", "views_update"]

    def test_the_blank_notice_is_in_french_for_a_french_reviewer(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """The notice and the form follow the locale recorded in the review view's metadata."""
        handle_redraft_action(ack, _redraft_body("  ", locale="fr-FR"), client)

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_review_view(
                    _EDITED_DRAFT, "fr-FR", _review_metadata("fr-FR"), notice=_NOTICES["fr-FR"]["redraft_blank"]
                ),
            )
        ]

    def test_an_unreadable_stage_rerenders_from_the_stored_draft(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """Without a readable stage the form values cannot be used, so the stored draft is shown again."""
        handle_redraft_action(ack, _redraft_body("", stage_value="not-a-stage"), client)

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_review_view(_DRAFT, "en-US", _review_metadata(), notice=_NOTICES["en-US"]["redraft_blank"]),
            )
        ]


class TestRedrafted:
    def test_acks_first_then_redrafts_with_the_form_values_as_the_base(
        self, ack: MagicMock, client: MagicMock, services: _Services, events: list[str]
    ) -> None:
        """The service gets the conversation, the reviewed sequence, the instructions, the edited values and the presser."""
        handle_redraft_action(ack, _redraft_body(), client)

        ack.assert_called_once_with()
        assert services.redraft_calls == [_redraft_call()]
        assert events == ["ack", "redraft_status_update", "views_update", "views_update"]

    def test_an_unreadable_stage_redrafts_from_the_stored_draft(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """When the stage cannot be parsed the stored draft is the model's base."""
        handle_redraft_action(ack, _redraft_body(stage_value="not-a-stage"), client)

        assert services.review_calls == [(_INCIDENT, _SEQUENCE)]
        assert services.redraft_calls == [_redraft_call(current=_STORED_EDIT)]

    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_shows_redrafting_then_the_review_form_of_the_new_draft(
        self, ack: MagicMock, client: MagicMock, services: _Services, locale: str
    ) -> None:
        """The modal shows the redrafting view, then the new draft's form with the new sequence, a notice and no instructions."""
        handle_redraft_action(ack, _redraft_body(locale=locale), client)

        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_redrafting_view(locale, _review_metadata(locale))),
            call(
                view_id=_VIEW_ID,
                hash=_NEXT_HASH,
                view=build_review_view(
                    _REDRAFTED,
                    locale,
                    _review_metadata(locale, sequence=_SEQUENCE + 1),
                    notice=_NOTICES[locale]["redrafted_note"],
                ),
            ),
        ]

    def test_the_new_form_metadata_names_the_new_sequence(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """Approving the redraft must target the new record, so the metadata carries its sequence."""
        handle_redraft_action(ack, _redraft_body(), client)

        last = client.views_update.call_args_list[-1].kwargs["view"]
        assert json.loads(last["private_metadata"]) == {
            "channel_id": _CHANNEL,
            "locale": "en-US",
            "incident_id": _INCIDENT,
            "sequence": _SEQUENCE + 1,
        }

    def test_only_updates_the_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """The only Slack calls are views_update: nothing is posted to the incident channel."""
        handle_redraft_action(ack, _redraft_body(), client)

        assert _client_method_names(client) == ["views_update", "views_update"]

    def test_slack_failures_are_not_raised(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A views.update exception never escapes the listener; the redraft still ran once."""
        client.views_update.side_effect = RuntimeError("view_not_found")

        handle_redraft_action(ack, _redraft_body(), client)

        assert services.redraft_calls == [_redraft_call()]


class TestFailureKeepsThePreviousDraft:
    @pytest.mark.parametrize(
        ("result", "notice_key"),
        [
            (OperationResult.transient_error(message="rate limited", error_code=ErrorCode.RATE_LIMITED), "redraft_failed"),
            (
                OperationResult.permanent_error(message="unreadable", error_code=DRAFT_UNPARSEABLE_CODE),
                "redraft_unparseable",
            ),
            (
                OperationResult.transient_error(message="store down", error_code=ErrorCode.STATUS_UPDATE_UNREADABLE),
                "redraft_failed",
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
        result: OperationResult[StatusUpdate],
        notice_key: str,
        locale: str,
    ) -> None:
        """After the redrafting view, the form is re-rendered from the reviewer's values with their instructions kept."""
        services.redraft_result = result

        handle_redraft_action(ack, _redraft_body(locale=locale), client)

        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_redrafting_view(locale, _review_metadata(locale))),
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

    def test_only_updates_the_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A failed redraft posts nothing either."""
        services.redraft_result = OperationResult.permanent_error(message="unreadable", error_code=DRAFT_UNPARSEABLE_CODE)

        handle_redraft_action(ack, _redraft_body(), client)

        assert _client_method_names(client) == ["views_update", "views_update"]


class TestSecurityConfirmation:
    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_a_refusal_rerenders_the_form_with_the_warning_and_the_checkbox(
        self, ack: MagicMock, client: MagicMock, services: _Services, locale: str
    ) -> None:
        """No model call was made, so there is no redrafting view: the form comes back with the warning, checkbox and instructions."""
        services.model_calls = 0
        services.redraft_result = OperationResult.permanent_error(
            message="confirm", error_code=ErrorCode.SECURITY_CONFIRMATION_REQUIRED
        )

        handle_redraft_action(ack, _redraft_body(locale=locale), client)

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_review_view(
                    _EDITED_DRAFT,
                    locale,
                    _review_metadata(locale),
                    notice=_NOTICES[locale]["redraft_security"],
                    instructions=_GUIDANCE,
                    security_confirm=True,
                ),
            )
        ]
        assert _client_method_names(client) == ["views_update"]

    def test_pressing_redraft_with_the_box_checked_passes_the_confirmation(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """The checked confirmation reaches the service as ``security_confirmed=True``."""
        handle_redraft_action(ack, _redraft_body(extra_values=_checkbox("confirmed")), client)

        assert services.redraft_calls == [_redraft_call(security_confirmed=True)]

    def test_an_unchecked_box_does_not_confirm(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """Showing the checkbox is not consent; left unchecked it passes ``security_confirmed=False``."""
        handle_redraft_action(ack, _redraft_body(extra_values=_checkbox()), client)

        assert services.redraft_calls == [_redraft_call(security_confirmed=False)]


class TestConflict:
    def test_an_append_conflict_shows_the_review_conflict_view(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """Another writer took the next sequence after the model answered: the modal says the draft changed elsewhere."""
        services.redraft_result = OperationResult.permanent_error(message="conflict", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)

        handle_redraft_action(ack, _redraft_body(), client)

        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_redrafting_view("en-US", _review_metadata())),
            call(
                view_id=_VIEW_ID,
                hash=_NEXT_HASH,
                view=build_review_error_view(ErrorCode.STATUS_UPDATE_CONFLICT, "en-US", _review_metadata()),
            ),
        ]

    def test_a_stale_draft_shows_the_review_conflict_view_without_redrafting_state(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """A draft that changed before the model was called shows the conflict view alone."""
        services.model_calls = 0
        services.redraft_result = OperationResult.permanent_error(message="conflict", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)

        handle_redraft_action(ack, _redraft_body(locale="fr-FR"), client)

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_review_error_view(ErrorCode.STATUS_UPDATE_CONFLICT, "fr-FR", _review_metadata("fr-FR")),
            )
        ]
