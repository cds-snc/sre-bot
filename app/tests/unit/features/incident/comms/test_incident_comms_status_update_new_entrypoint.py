"""Tests for starting a status update by hand from the status-updates modal.

The New update button calls ``start_status_update_draft`` and replaces the
modal with the review form for the returned draft, hand-started or already
pending. The form carries the AI section only when text generation is
configured. ``start_status_update_draft`` is patched with a ``MagicMock``, the
availability predicate with a constant, and the Slack client is a
``MagicMock``, so the tests assert the service arguments and the view sent to
``views.update``; one test binds the real service to a core
``InMemoryStatusUpdateStore``, a stub lookup and a stub transcript reader to
assert the stored record.
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.comms import form
from features.incident.comms.domain import StatusUpdateDraftOutcome, StatusUpdateOutcomeKind
from features.incident.comms.entrypoints.slack import handle_new_update_action, register
from features.incident.comms.entrypoints.slack_views import NEW_ACTION_ID, REVIEW_CALLBACK_ID, build_review_view
from features.incident.comms.service import start_status_update_draft
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_USER = "U123"
_VIEW_ID = "V456"
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_TARGET = "features.incident.comms.form.start_status_update_draft"
_METADATA = {"channel_id": _CHANNEL, "locale": "en-US", "incident_id": _INCIDENT, "sequence": 4}


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


_DRAFT = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=4,
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


class _StubLookup:
    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        return OperationResult.success(data=_INCIDENT)


class _StubReader:
    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        return _NOW - timedelta(hours=2)

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> Sequence[TranscriptMessage]:
        return (TranscriptMessage(author="Ada", text="DNS is failing", posted_at=_NOW - timedelta(minutes=5)),)


def _body() -> dict[str, Any]:
    return {
        "type": "block_actions",
        "user": {"id": _USER},
        "view": {"id": _VIEW_ID, "hash": "h1", "private_metadata": json.dumps({"channel_id": _CHANNEL, "locale": "en-US"})},
        "actions": [{"action_id": NEW_ACTION_ID, "block_id": "overview_actions", "type": "button"}],
    }


def _service(kind: StatusUpdateOutcomeKind) -> MagicMock:
    return MagicMock(return_value=OperationResult.success(data=StatusUpdateDraftOutcome(update=_DRAFT, kind=kind)))


@pytest.fixture(autouse=True)
def _ai_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Text generation is configured unless a test says otherwise."""
    monkeypatch.setattr(form, "text_generation_available", lambda: True)


def _sent_view(client: MagicMock) -> dict[str, Any]:
    (call,) = client.views_update.call_args_list
    assert call.kwargs["view_id"] == _VIEW_ID
    view: dict[str, Any] = call.kwargs["view"]
    return view


def _block_ids(view: dict[str, Any]) -> list[str | None]:
    return [block.get("block_id") for block in view["blocks"]]


class TestNewUpdateAction:
    def test_acks_then_starts_a_draft_by_this_responder_in_this_channel(self) -> None:
        """The service is asked to start a draft for the channel, written by the presser; nothing else is passed."""
        ack = MagicMock()
        service = _service(StatusUpdateOutcomeKind.MANUAL)

        with patch(_TARGET, new=service):
            handle_new_update_action(ack, _body(), MagicMock())

        ack.assert_called_once()
        assert (service.call_args.args, service.call_args.kwargs) == ((_CHANNEL,), {"author": _USER})

    def test_stores_a_blank_hand_written_draft_and_shows_its_form(self) -> None:
        """With the real service, the first update is stored as a blank HAND draft by the presser and its form is shown."""
        store = InMemoryStatusUpdateStore()
        client = MagicMock()
        service = partial(start_status_update_draft, lookup=_StubLookup(), reader=_StubReader(), store=store, now=_NOW)

        with patch(_TARGET, new=service):
            handle_new_update_action(MagicMock(), _body(), client)

        assert store.list_for_incident(_INCIDENT).data is not None
        (stored,) = store.list_for_incident(_INCIDENT).data
        assert (stored.sequence, stored.state, stored.author, stored.origin) == (
            1,
            StatusUpdateState.DRAFT,
            _USER,
            StatusUpdateOrigin.HAND,
        )
        assert stored.en == StatusUpdateText(affected_service="", impact="", current_action="", workaround="")
        view = _sent_view(client)
        assert view["callback_id"] == REVIEW_CALLBACK_ID
        assert json.loads(view["private_metadata"])["sequence"] == 1
        client.chat_postMessage.assert_not_called()

    @pytest.mark.parametrize("kind", [StatusUpdateOutcomeKind.MANUAL, StatusUpdateOutcomeKind.PENDING])
    def test_the_draft_opens_in_the_form_with_the_ai_section_and_no_notice(self, kind: StatusUpdateOutcomeKind) -> None:
        """A started or already pending draft opens on the form, with Draft with AI offered and nothing to explain."""
        client = MagicMock()

        with patch(_TARGET, new=_service(kind)):
            handle_new_update_action(MagicMock(), _body(), client)

        assert _sent_view(client) == build_review_view(_DRAFT, "en-US", json.dumps(_METADATA), with_ai=True)

    def test_without_text_generation_the_form_has_no_ai_section(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With the generator unconfigured the form opens on the stage select; Save draft and Approve remain."""
        monkeypatch.setattr(form, "text_generation_available", lambda: False)
        client = MagicMock()

        with patch(_TARGET, new=_service(StatusUpdateOutcomeKind.MANUAL)):
            handle_new_update_action(MagicMock(), _body(), client)

        view = _sent_view(client)
        assert view == build_review_view(_DRAFT, "en-US", json.dumps(_METADATA), with_ai=False)
        assert _block_ids(view)[0] == "stage"

    def test_a_refusal_shows_the_error_view(self) -> None:
        """With no conversation to write about, the modal shows the localized error with Close."""
        client = MagicMock()
        refusal = OperationResult.permanent_error(message="empty", error_code=ErrorCode.EMPTY_HISTORY)

        with patch(_TARGET, new=MagicMock(return_value=refusal)):
            handle_new_update_action(MagicMock(), _body(), client)

        view = _sent_view(client)
        assert "callback_id" not in view
        assert view["blocks"][0]["text"]["text"] == "There is no channel history to draft a status update from yet."


def test_register_includes_the_new_update_action() -> None:
    """The New update button is registered as a block action with its own listener."""
    registrar = MagicMock()

    register(registrar)

    registered = {call.args[0]: call.args[1] for call in registrar.register_block_action.call_args_list}
    assert registered[NEW_ACTION_ID] is handle_new_update_action
