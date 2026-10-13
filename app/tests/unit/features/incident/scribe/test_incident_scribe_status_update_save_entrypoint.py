"""Tests for the Save draft button listener of the review modal.

The listener acks, reads the responder's stage and fields from the action's
view state, saves them through the service and shows the form of the saved
draft with a notice. A stale sequence shows the review conflict view; any other
failure, or a form with no readable stage, re-renders the form from the typed
values over the stored draft with a failure notice. Every outcome is one
``views_update`` of the pressed modal; nothing is posted to a channel.

The service boundary is stubbed with recording fakes in the entrypoint module's
namespace (``save_status_update_draft`` and ``get_draft_for_review``) that
return real ``OperationResult`` values, and the Slack client is a
``MagicMock``. Expected views come from the view builders and notice wording is
pinned literally (the catalogue is not loaded in unit tests), so each
assertion compares the exact view sent.
"""

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from features.incident.scribe import status_update_form
from features.incident.scribe.domain import StatusUpdateEdit
from features.incident.scribe.entrypoints.slack import handle_save_action, register
from features.incident.scribe.entrypoints.slack_views import (
    REVIEW_CALLBACK_ID,
    SAVE_ACTION_ID,
    build_review_error_view,
    build_review_view,
)

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_USER = "U0SAVER"
_SEQUENCE = 3
_VIEW_ID = "VREVIEW"
_VIEW_HASH = "review-hash=="
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_SAVED_NOTE = {"en-US": "Draft saved.", "fr-FR": "Brouillon enregistré."}
_SAVE_FAILED = {
    "en-US": "The draft could not be saved; your text is still here.",
    "fr-FR": "Le brouillon n'a pas pu être enregistré; votre texte est toujours là.",
}


def _text(language: str, prefix: str = "") -> StatusUpdateText:
    return StatusUpdateText(**{name: f"{prefix}{language} {name}" for name in _FIELDS})


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
_EDIT = StatusUpdateEdit(stage=StatusUpdateStage.MONITORING, en=_text("en", "typed "), fr=_text("fr", "typed "))
_SAVED = replace(_DRAFT, sequence=_SEQUENCE + 1, stage=_EDIT.stage, en=_EDIT.en, fr=_EDIT.fr, author=_USER)


def _metadata(locale: str, sequence: int) -> str:
    return json.dumps({"channel_id": _CHANNEL, "locale": locale, "incident_id": _INCIDENT, "sequence": sequence})


def _values(edit: StatusUpdateEdit | None) -> dict[str, Any]:
    if edit is None:
        return {"stage": {"stage": {"type": "static_select", "selected_option": None}}}
    values: dict[str, Any] = {
        f"{language}.{name}": {"text": {"type": "plain_text_input", "value": getattr(text, name) or None}}
        for language, text in (("en", edit.en), ("fr", edit.fr))
        for name in _FIELDS
    }
    option = {"text": {"type": "plain_text", "text": edit.stage.value}, "value": edit.stage.value}
    values["stage"] = {"stage": {"type": "static_select", "selected_option": option}}
    return values


def _body(edit: StatusUpdateEdit | None = _EDIT, locale: str = "en-US") -> dict[str, Any]:
    return {
        "type": "block_actions",
        "user": {"id": _USER},
        "view": {
            "id": _VIEW_ID,
            "hash": _VIEW_HASH,
            "callback_id": REVIEW_CALLBACK_ID,
            "private_metadata": _metadata(locale, _SEQUENCE),
            "state": {"values": _values(edit)},
        },
        "actions": [{"action_id": SAVE_ACTION_ID, "block_id": "save_button", "type": "button"}],
    }


@dataclass
class _Services:
    """Recording fakes for the save service and the review read, sharing one event log with ack and the client."""

    saved: OperationResult[StatusUpdate]
    stored: OperationResult[StatusUpdate]
    events: list[str] = field(default_factory=list)
    save_calls: list[dict[str, Any]] = field(default_factory=list)
    read_calls: list[tuple[str, int]] = field(default_factory=list)

    def save(self, conversation_id: str, sequence: int, *, edit: StatusUpdateEdit, author: str) -> OperationResult[StatusUpdate]:
        self.events.append("save")
        self.save_calls.append({"conversation_id": conversation_id, "sequence": sequence, "edit": edit, "author": author})
        return self.saved

    async def read(self, incident_id: str, sequence: int) -> OperationResult[StatusUpdate]:
        self.events.append("read")
        self.read_calls.append((incident_id, sequence))
        return self.stored


def _install(monkeypatch: pytest.MonkeyPatch, saved: OperationResult[StatusUpdate]) -> _Services:
    services = _Services(saved=saved, stored=OperationResult.success(data=_DRAFT))
    monkeypatch.setattr(status_update_form, "save_status_update_draft", services.save)
    monkeypatch.setattr(status_update_form, "get_draft_for_review", services.read)
    monkeypatch.setattr(status_update_form, "text_generation_available", lambda: True)
    return services


def _client(services: _Services) -> MagicMock:
    client = MagicMock()
    client.views_update.side_effect = lambda **_: services.events.append("views_update") or {"view": {"hash": "next"}}
    return client


def _sent_view(client: MagicMock) -> dict[str, Any]:
    (sent,) = client.views_update.call_args_list
    assert (sent.kwargs["view_id"], sent.kwargs["hash"]) == (_VIEW_ID, _VIEW_HASH)
    view: dict[str, Any] = sent.kwargs["view"]
    return view


class TestSaved:
    def test_acks_then_saves_the_typed_values_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ack comes first, then one save of the typed stage and fields at the form's sequence by the presser."""
        services = _install(monkeypatch, OperationResult.success(data=_SAVED))
        ack = MagicMock(side_effect=lambda: services.events.append("ack"))

        handle_save_action(ack, _body(), _client(services))

        assert services.events == ["ack", "save", "views_update"]
        assert services.save_calls == [{"conversation_id": _CHANNEL, "sequence": _SEQUENCE, "edit": _EDIT, "author": _USER}]

    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_shows_the_saved_draft_form_for_the_new_sequence(self, monkeypatch: pytest.MonkeyPatch, locale: str) -> None:
        """The form re-renders from the stored record with the saved notice, so the next save or approval targets it."""
        services = _install(monkeypatch, OperationResult.success(data=_SAVED))
        client = _client(services)

        handle_save_action(MagicMock(), _body(locale=locale), client)

        assert _sent_view(client) == build_review_view(
            _SAVED, locale, _metadata(locale, _SEQUENCE + 1), notice=_SAVED_NOTE[locale]
        )

    def test_without_text_generation_the_saved_form_has_no_ai_section(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With the generator unconfigured the re-rendered form leaves the AI section out."""
        services = _install(monkeypatch, OperationResult.success(data=_SAVED))
        monkeypatch.setattr(status_update_form, "text_generation_available", lambda: False)
        client = _client(services)

        handle_save_action(MagicMock(), _body(), client)

        assert not {"instructions", "generate_button"} & {block.get("block_id") for block in _sent_view(client)["blocks"]}

    def test_partial_fields_are_saved_as_typed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unfinished draft is saved: cleared fields reach the service as empty strings, not as a refusal."""
        partial = StatusUpdateEdit(stage=_EDIT.stage, en=replace(_EDIT.en, impact="", workaround=""), fr=_EDIT.fr)
        services = _install(monkeypatch, OperationResult.success(data=_SAVED))

        handle_save_action(MagicMock(), _body(partial), _client(services))

        assert services.save_calls[0]["edit"] == partial

    def test_nothing_is_posted_to_the_channel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Saving touches only the modal."""
        services = _install(monkeypatch, OperationResult.success(data=_SAVED))
        client = _client(services)

        handle_save_action(MagicMock(), _body(), client)

        client.chat_postMessage.assert_not_called()
        client.chat_postEphemeral.assert_not_called()


class TestNotSaved:
    def test_a_stale_sequence_shows_the_conflict_view(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Another draft took the sequence, so the modal says so instead of overwriting it; the stored draft is not read."""
        conflict = OperationResult.permanent_error(message="stale", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)
        services = _install(monkeypatch, conflict)
        client = _client(services)

        handle_save_action(MagicMock(), _body(), client)

        assert _sent_view(client) == build_review_error_view(
            ErrorCode.STATUS_UPDATE_CONFLICT, "en-US", _metadata("en-US", _SEQUENCE)
        )
        assert services.read_calls == []

    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_a_store_failure_keeps_the_typed_values(self, monkeypatch: pytest.MonkeyPatch, locale: str) -> None:
        """The form comes back with what the responder typed over the stored draft, and a notice that nothing was saved."""
        failure = OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED)
        services = _install(monkeypatch, failure)
        client = _client(services)

        handle_save_action(MagicMock(), _body(locale=locale), client)

        typed = replace(_DRAFT, stage=_EDIT.stage, en=_EDIT.en, fr=_EDIT.fr)
        assert _sent_view(client) == build_review_view(typed, locale, _metadata(locale, _SEQUENCE), notice=_SAVE_FAILED[locale])
        assert services.read_calls == [(_INCIDENT, _SEQUENCE)]

    def test_a_failed_read_after_a_failed_save_shows_the_error_view(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With neither the save nor the stored draft available, the modal shows the read's error with Close."""
        failure = OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED)
        services = _install(monkeypatch, failure)
        services.stored = OperationResult.transient_error(message="down", error_code=ErrorCode.SERVER_ERROR)
        client = _client(services)

        handle_save_action(MagicMock(), _body(), client)

        assert _sent_view(client) == build_review_error_view(ErrorCode.SERVER_ERROR, "en-US", _metadata("en-US", _SEQUENCE))

    def test_a_form_without_a_stage_is_not_saved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unreadable stage cannot be stored, so nothing is saved and the stored draft's form returns with the notice."""
        services = _install(monkeypatch, OperationResult.success(data=_SAVED))
        client = _client(services)

        handle_save_action(MagicMock(), _body(None), client)

        assert services.save_calls == []
        assert _sent_view(client) == build_review_view(
            _DRAFT, "en-US", _metadata("en-US", _SEQUENCE), notice=_SAVE_FAILED["en-US"]
        )

    def test_a_slack_update_failure_is_logged_not_raised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failed views.update leaves the saved draft in place and does not raise out of the listener."""
        _install(monkeypatch, OperationResult.success(data=_SAVED))
        client = MagicMock()
        client.views_update.side_effect = RuntimeError("slack down")

        handle_save_action(MagicMock(), _body(), client)

        client.views_update.assert_called_once()


def test_register_includes_the_save_action() -> None:
    """The Save draft button is registered as a block action with its own listener."""
    registrar = MagicMock()

    register(registrar)

    registered = {call.args[0]: call.args[1] for call in registrar.register_block_action.call_args_list}
    assert registered[SAVE_ACTION_ID] is handle_save_action
