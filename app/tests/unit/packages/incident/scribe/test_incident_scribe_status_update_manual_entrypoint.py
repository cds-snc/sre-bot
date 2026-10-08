"""Tests for writing a status update by hand from the status-updates modal.

The Write it myself button runs the status-update service with ``manual=True``
and replaces the modal with the review form for the returned draft. A Draft
press whose model call failed comes back as a ``MANUAL`` outcome and lands on
the same form with a notice. A hand-written draft has no Redraft section; a
pending AI draft opened through Write keeps it. ``draft_status_update`` is
patched with an ``AsyncMock`` and the Slack client is a ``MagicMock``, so the
tests assert the service arguments and the view sent to ``views.update``.
"""

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.domain import StatusUpdateDraftOutcome, StatusUpdateOutcomeKind
from packages.incident.scribe.entrypoints.slack import handle_draft_action, handle_write_action, register
from packages.incident.scribe.platforms.slack import REVIEW_CALLBACK_ID, WRITE_ACTION_ID

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


def _body() -> dict[str, Any]:
    return {
        "type": "block_actions",
        "user": {"id": _USER},
        "view": {"id": _VIEW_ID, "hash": "h1", "private_metadata": json.dumps({"channel_id": _CHANNEL, "locale": "en-US"})},
        "actions": [{"action_id": WRITE_ACTION_ID, "block_id": "draft_button", "type": "button"}],
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


class TestWriteAction:
    def test_acks_then_runs_the_service_in_manual_mode(self) -> None:
        """The service is asked for a hand-written draft by this responder in this channel, with no security confirmation."""
        ack = MagicMock()
        service = _service(StatusUpdateOutcomeKind.MANUAL)

        with patch(_TARGET, new=service):
            handle_write_action(ack, _body(), MagicMock())

        ack.assert_called_once()
        assert service.call_args.args == (_CHANNEL,)
        assert (service.call_args.kwargs["author"], service.call_args.kwargs["manual"]) == (_USER, True)
        assert service.call_args.kwargs["security_confirmed"] is False

    def test_a_manual_draft_opens_the_review_form_without_redraft_or_notice(self) -> None:
        """The responder chose to write, so the form opens on the fields with nothing to explain and no AI to ask."""
        client = MagicMock()

        with patch(_TARGET, new=_service(StatusUpdateOutcomeKind.MANUAL)):
            handle_write_action(MagicMock(), _body(), client)

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
            handle_write_action(MagicMock(), _body(), client)

        view = _sent_view(client)
        assert view["callback_id"] == REVIEW_CALLBACK_ID
        assert _block_ids(view)[:3] == ["instructions", "redraft_button", "stage"]

    def test_a_refusal_shows_the_error_view(self) -> None:
        """With no conversation to write about, the modal shows the localized error with Close, as Draft does."""
        client = MagicMock()
        refusal = OperationResult.permanent_error(message="empty", error_code=ErrorCode.EMPTY_HISTORY)

        with patch(_TARGET, new=AsyncMock(return_value=refusal)):
            handle_write_action(MagicMock(), _body(), client)

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


def test_register_includes_the_write_action() -> None:
    """The Write it myself button is registered as a block action with its own listener."""
    registrar = MagicMock()

    register(registrar)

    registered = {call.args[0]: call.args[1] for call in registrar.register_block_action.call_args_list}
    assert registered[WRITE_ACTION_ID] is handle_write_action
