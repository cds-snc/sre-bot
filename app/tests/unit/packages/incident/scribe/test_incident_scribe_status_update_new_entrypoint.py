"""Tests for starting a status update by hand from the status-updates modal.

The New update button runs the status-update service with ``manual=True``
and replaces the modal with the review form for the returned draft. A Draft
press whose model call failed comes back as a ``MANUAL`` outcome and lands on
the same form with a notice. A hand-written draft has no Redraft section; a
pending AI draft opened through New update keeps it. ``draft_status_update`` is
patched with an ``AsyncMock`` and the Slack client is a ``MagicMock``, so the
tests assert the service arguments and the view sent to ``views.update``; one
test binds the real service to a core ``InMemoryStatusUpdateStore``, a stub
lookup and a stub transcript reader to assert the stored record.
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from packages.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from packages.incident.core.api import (
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)
from packages.incident.scribe.domain import StatusUpdateDraftOutcome, StatusUpdateOutcomeKind
from packages.incident.scribe.entrypoints.slack import handle_draft_action, handle_new_update_action, register
from packages.incident.scribe.entrypoints.slack_views import NEW_ACTION_ID, REVIEW_CALLBACK_ID
from packages.incident.scribe.status_update import draft_status_update

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_USER = "U123"
_VIEW_ID = "V456"
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_TARGET = "packages.incident.scribe.entrypoints.slack.draft_status_update"
_FALLBACK = "AI drafting isn't available right now. Write the update in the fields below, then press Approve."


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
        "actions": [{"action_id": NEW_ACTION_ID, "block_id": "draft_button", "type": "button"}],
    }


def _service(kind: StatusUpdateOutcomeKind) -> AsyncMock:
    return AsyncMock(return_value=OperationResult.success(data=StatusUpdateDraftOutcome(update=_DRAFT, kind=kind)))


def _sent_view(client: MagicMock) -> dict[str, Any]:
    (call,) = client.views_update.call_args_list
    assert call.kwargs["view_id"] == _VIEW_ID
    view: dict[str, Any] = call.kwargs["view"]
    return view


def _block_ids(view: dict[str, Any]) -> list[str | None]:
    return [block.get("block_id") for block in view["blocks"]]


class TestNewUpdateAction:
    def test_acks_then_runs_the_service_in_manual_mode(self) -> None:
        """The service is asked for a hand-written draft by this responder in this channel, with no security confirmation."""
        ack = MagicMock()
        service = _service(StatusUpdateOutcomeKind.MANUAL)

        with patch(_TARGET, new=service):
            handle_new_update_action(ack, _body(), MagicMock())

        ack.assert_called_once()
        assert service.call_args.args == (_CHANNEL,)
        assert (service.call_args.kwargs["author"], service.call_args.kwargs["manual"]) == (_USER, True)
        assert service.call_args.kwargs["security_confirmed"] is False

    def test_stores_a_blank_hand_written_draft_and_shows_its_form(self) -> None:
        """With the real service, the first update is stored as a blank HAND draft by the presser and its form is shown."""
        store = InMemoryStatusUpdateStore()
        client = MagicMock()
        service = partial(draft_status_update, lookup=_StubLookup(), reader=_StubReader(), store=store, now=_NOW)

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

    def test_a_manual_draft_opens_the_review_form_without_redraft_or_notice(self) -> None:
        """The responder chose to write, so the form opens on the fields with nothing to explain and no AI to ask."""
        client = MagicMock()

        with patch(_TARGET, new=_service(StatusUpdateOutcomeKind.MANUAL)):
            handle_new_update_action(MagicMock(), _body(), client)

        view = _sent_view(client)
        assert view["callback_id"] == REVIEW_CALLBACK_ID
        assert json.loads(view["private_metadata"]) == {
            "channel_id": _CHANNEL,
            "locale": "en-US",
            "incident_id": _INCIDENT,
            "sequence": 4,
        }
        assert view["blocks"][0]["block_id"] == "stage"

    @pytest.mark.parametrize("kind", [StatusUpdateOutcomeKind.PENDING, StatusUpdateOutcomeKind.CARRIED_FORWARD])
    def test_an_existing_or_carried_draft_opens_the_review_form_with_redraft(self, kind: StatusUpdateOutcomeKind) -> None:
        """A draft that was not written by hand can still be redrafted, so its form keeps the Redraft section."""
        client = MagicMock()

        with patch(_TARGET, new=_service(kind)):
            handle_new_update_action(MagicMock(), _body(), client)

        view = _sent_view(client)
        assert view["callback_id"] == REVIEW_CALLBACK_ID
        assert _block_ids(view)[:3] == ["instructions", "redraft_button", "stage"]

    def test_a_refusal_shows_the_error_view(self) -> None:
        """With no conversation to write about, the modal shows the localized error with Close, as Draft does."""
        client = MagicMock()
        refusal = OperationResult.permanent_error(message="empty", error_code=ErrorCode.EMPTY_HISTORY)

        with patch(_TARGET, new=AsyncMock(return_value=refusal)):
            handle_new_update_action(MagicMock(), _body(), client)

        view = _sent_view(client)
        assert "callback_id" not in view
        assert view["blocks"][0]["text"]["text"] == "There is no channel history to draft a status update from yet."


class TestDraftFallback:
    def test_a_failed_draft_opens_the_review_form_with_the_fallback_notice(self) -> None:
        """When the model could not draft, the responder lands on the form with a notice saying why, and no Redraft."""
        client = MagicMock()

        with patch(_TARGET, new=_service(StatusUpdateOutcomeKind.MANUAL)) as service:
            handle_draft_action(MagicMock(), _body(), client)

        assert service.call_args.kwargs["manual"] is False
        view = _sent_view(client)
        assert view["callback_id"] == REVIEW_CALLBACK_ID
        assert view["blocks"][0] == {"type": "section", "text": {"type": "mrkdwn", "text": _FALLBACK}}
        assert _block_ids(view)[1] == "stage"


def test_register_includes_the_new_update_action() -> None:
    """The New update button is registered as a block action with its own listener."""
    registrar = MagicMock()

    register(registrar)

    registered = {call.args[0]: call.args[1] for call in registrar.register_block_action.call_args_list}
    assert registered[NEW_ACTION_ID] is handle_new_update_action
