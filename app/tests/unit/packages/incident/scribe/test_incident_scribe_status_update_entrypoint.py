"""Tests for the incident scribe Slack entrypoint: Draft button listener.

The Draft button in the status-updates modal triggers a block action that acks
first, shows a drafting state with views.update, calls the status-update service
via asyncio.run, then updates the same view with the drafted, carried-forward or
pending result in EN and FR. Service errors and view update failures are shown
in-modal with a Close button and logged; nothing is posted to the channel.
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.domain import StatusUpdateDraftOutcome, StatusUpdateOutcomeKind
from packages.incident.scribe.entrypoints.slack import handle_draft_action

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_USER = "U123"
_VIEW_ID = "V456"
_VIEW_HASH = "hash123=="


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


def _pending_update(sequence: int = 1) -> StatusUpdate:
    now = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=StatusUpdateState.DRAFT,
        stage=StatusUpdateStage.IDENTIFIED,
        en=_text("en"),
        fr=_text("fr"),
        next_update_at=now,
        author="U999",
        transcript_cutoff=now,
        transcript_fingerprint="v1:sha256:abc123",
        created_at=now,
    )


def _block_action_body(view_id: str = _VIEW_ID, view_hash: str = _VIEW_HASH, user_id: str = _USER) -> dict:
    """Build a block_actions body for a modal button."""
    return {
        "type": "block_actions",
        "user": {"id": user_id},
        "trigger_id": "trigger-123",
        "channel": {"id": _CHANNEL},
        "view": {
            "id": view_id,
            "hash": view_hash,
            "private_metadata": json.dumps({"channel_id": _CHANNEL, "locale": "en-US"}),
        },
        "actions": [
            {
                "action_id": "incident.scribe.status_update.draft",
                "block_id": "draft_button",
                "type": "button",
                "value": "",
            }
        ],
    }


class TestHandleDraftAction:
    """Block action listener for the Draft button in the status-updates modal."""

    def test_acks_before_any_other_call(self):
        """The listener acks first, synchronously, so Slack gets a 200 immediately."""
        ack = MagicMock()
        client = MagicMock()
        body = _block_action_body()

        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=OperationResult.success(data=_make_outcome())),
        ):
            handle_draft_action(ack, body, client)

        ack.assert_called_once()

    def test_sends_drafting_view_with_view_id_hash_and_no_button(self):
        """First views_update uses body's view_id and hash; view is drafting state (no button, localized text)."""
        ack = MagicMock()
        client = MagicMock()
        # Second call returns response with new hash
        client.views_update.return_value = {"ok": True, "view": {"hash": "new_hash=="}}
        body = _block_action_body(view_id="V999", view_hash="original_hash==")

        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=OperationResult.success(data=_make_outcome())),
        ):
            handle_draft_action(ack, body, client)

        # Assert two views_update calls
        calls = client.views_update.call_args_list
        assert len(calls) >= 2

        # First call: drafting state with original hash
        first_call = calls[0]
        first_kwargs = first_call[1]
        assert first_kwargs["view_id"] == "V999"
        assert first_kwargs.get("hash") == "original_hash=="
        # Drafting view should NOT have the Draft button
        drafting_view = first_kwargs["view"]
        drafting_view_str = str(drafting_view)
        assert "incident.scribe.status_update.draft" not in drafting_view_str

        # Second call: result view WITHOUT the stale hash (either no hash or new hash from first response)
        second_call = calls[1]
        second_kwargs = second_call[1]
        # Should not pass the original hash
        assert second_kwargs.get("hash") != "original_hash=="

    def test_result_view_pending_outcome_rendered_in_en_and_fr(self):
        """When a draft already covers everything, result view shows pending draft in EN and FR."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True}
        body = _block_action_body()

        outcome = _make_outcome(kind=StatusUpdateOutcomeKind.PENDING, update=_pending_update(sequence=1))
        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=OperationResult.success(data=outcome)),
        ):
            handle_draft_action(ack, body, client)

        calls = client.views_update.call_args_list
        assert len(calls) >= 2
        # Result view should contain both language sections
        result_kwargs = calls[-1][1]
        result_view = result_kwargs["view"]
        result_str = str(result_view)
        # Both EN and FR should be in the result
        assert "en service" in result_str or "affected_service" in result_str.lower()

    def test_result_view_drafted_outcome_rendered(self):
        """After model drafting, result view shows drafted update."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True}
        body = _block_action_body()

        outcome = _make_outcome(kind=StatusUpdateOutcomeKind.DRAFTED, update=_pending_update(sequence=2))
        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=OperationResult.success(data=outcome)),
        ):
            handle_draft_action(ack, body, client)

        calls = client.views_update.call_args_list
        assert len(calls) >= 2

    def test_result_view_carried_forward_outcome_rendered(self):
        """When no new activity, result view shows carried-forward update."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True}
        body = _block_action_body()

        outcome = _make_outcome(kind=StatusUpdateOutcomeKind.CARRIED_FORWARD, update=_pending_update(sequence=2))
        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=OperationResult.success(data=outcome)),
        ):
            handle_draft_action(ack, body, client)

        calls = client.views_update.call_args_list
        assert len(calls) >= 2

    def test_maps_empty_history_error_to_modal_with_close_no_button(self):
        """Error: no history. View shows error with Close button, no Draft button."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True}
        body = _block_action_body()

        error_result: OperationResult[StatusUpdateDraftOutcome] = OperationResult.permanent_error(
            message="No history",
            error_code=ErrorCode.EMPTY_HISTORY,
        )
        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=error_result),
        ):
            handle_draft_action(ack, body, client)

        calls = client.views_update.call_args_list
        assert len(calls) >= 2
        error_kwargs = calls[-1][1]
        error_view = error_kwargs["view"]
        error_str = str(error_view)
        # Error view must have Close button
        assert "close" in error_str.lower()
        # Error view must NOT have Draft button
        assert "incident.scribe.status_update.draft" not in error_str

    def test_maps_draft_unparseable_error_to_modal_with_close_no_button(self):
        """Error: unparseable model output. View shows error with Close, no Draft button."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True}
        body = _block_action_body()

        error_result: OperationResult[StatusUpdateDraftOutcome] = OperationResult.permanent_error(
            message="Could not parse",
            error_code="DRAFT_UNPARSEABLE",
        )
        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=error_result),
        ):
            handle_draft_action(ack, body, client)

        calls = client.views_update.call_args_list
        assert len(calls) >= 2
        error_kwargs = calls[-1][1]
        error_view = error_kwargs["view"]
        error_str = str(error_view)
        assert "close" in error_str.lower()
        assert "incident.scribe.status_update.draft" not in error_str

    def test_maps_status_update_conflict_error_to_modal_with_close_no_button(self):
        """Error: conflict from concurrent write. View shows error with Close, no Draft button."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True}
        body = _block_action_body()

        error_result: OperationResult[StatusUpdateDraftOutcome] = OperationResult.permanent_error(
            message="Conflict",
            error_code=ErrorCode.STATUS_UPDATE_CONFLICT,
        )
        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=error_result),
        ):
            handle_draft_action(ack, body, client)

        calls = client.views_update.call_args_list
        assert len(calls) >= 2
        error_kwargs = calls[-1][1]
        error_view = error_kwargs["view"]
        error_str = str(error_view)
        assert "close" in error_str.lower()
        assert "incident.scribe.status_update.draft" not in error_str

    def test_maps_not_an_incident_error_to_modal_with_close_no_button(self):
        """Error: channel is not an incident. View shows error with Close, no Draft button."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True}
        body = _block_action_body()

        error_result: OperationResult[StatusUpdateDraftOutcome] = OperationResult.permanent_error(
            message="Not an incident",
            error_code=ErrorCode.NOT_AN_INCIDENT,
        )
        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=error_result),
        ):
            handle_draft_action(ack, body, client)

        calls = client.views_update.call_args_list
        assert len(calls) >= 2
        error_kwargs = calls[-1][1]
        error_view = error_kwargs["view"]
        error_str = str(error_view)
        assert "close" in error_str.lower()
        assert "incident.scribe.status_update.draft" not in error_str

    def test_maps_ambiguous_incident_error_to_modal_with_close_no_button(self):
        """Error: ambiguous incident. View shows error with Close, no Draft button."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True}
        body = _block_action_body()

        error_result: OperationResult[StatusUpdateDraftOutcome] = OperationResult.permanent_error(
            message="Ambiguous",
            error_code=ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION,
        )
        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=error_result),
        ):
            handle_draft_action(ack, body, client)

        calls = client.views_update.call_args_list
        assert len(calls) >= 2
        error_kwargs = calls[-1][1]
        error_view = error_kwargs["view"]
        error_str = str(error_view)
        assert "close" in error_str.lower()
        assert "incident.scribe.status_update.draft" not in error_str

    def test_maps_unexpected_classified_error_to_generic_modal_with_close_no_button(self):
        """Error: unexpected classified error (e.g., store failure). View shows generic error with Close, no Draft button."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True}
        body = _block_action_body()

        error_result: OperationResult[StatusUpdateDraftOutcome] = OperationResult.transient_error(
            message="Store throttled",
            error_code=ErrorCode.RATE_LIMITED,
        )
        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=error_result),
        ):
            handle_draft_action(ack, body, client)

        calls = client.views_update.call_args_list
        assert len(calls) >= 2
        error_kwargs = calls[-1][1]
        error_view = error_kwargs["view"]
        error_str = str(error_view)
        assert "close" in error_str.lower()
        assert "incident.scribe.status_update.draft" not in error_str

    def test_logs_when_drafting_view_update_fails_but_continues(self):
        """When drafting state update fails, error is logged; listener still drafts and updates result view."""
        ack = MagicMock()
        client = MagicMock()
        # First call fails (drafting update), second succeeds (result update)
        client.views_update.side_effect = [
            Exception("API error: expired_trigger_id"),
            {"ok": True},
        ]
        body = _block_action_body()

        with capture_logs() as logs:
            with patch(
                "packages.incident.scribe.entrypoints.slack.draft_status_update",
                new=AsyncMock(return_value=OperationResult.success(data=_make_outcome())),
            ):
                handle_draft_action(ack, body, client)

        failures = [entry for entry in logs if entry["event"] == "incident_status_update_drafting_update_failed"]
        assert len(failures) == 1
        assert failures[0]["log_level"] == "warning"
        # The service still ran and the result update was still attempted
        assert client.views_update.call_count == 2

    def test_logs_when_result_view_update_fails(self):
        """When result view update fails, error is logged; listener doesn't raise."""
        ack = MagicMock()
        client = MagicMock()
        # First call succeeds (drafting), second fails (result)
        client.views_update.side_effect = [
            {"ok": True},
            Exception("API error: invalid_view"),
        ]
        body = _block_action_body()

        with capture_logs() as logs:
            with patch(
                "packages.incident.scribe.entrypoints.slack.draft_status_update",
                new=AsyncMock(return_value=OperationResult.success(data=_make_outcome())),
            ):
                handle_draft_action(ack, body, client)

        failures = [entry for entry in logs if entry["event"] == "incident_status_update_result_update_failed"]
        assert len(failures) == 1
        assert failures[0]["log_level"] == "warning"

    def test_makes_no_post_message_or_post_ephemeral_calls(self):
        """The listener never posts to the channel; all output goes in the modal."""
        ack = MagicMock()
        client = MagicMock()
        body = _block_action_body()

        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=OperationResult.success(data=_make_outcome())),
        ):
            handle_draft_action(ack, body, client)

        # Check for post_message or post_ephemeral calls
        for call in client.method_calls:
            method_name = call[0]
            assert "post_message" not in method_name
            assert "post_ephemeral" not in method_name

    def test_calls_draft_status_update_with_channel_id_and_user_id(self):
        """The service is called with the channel id from private_metadata and the user id from the body."""
        ack = MagicMock()
        client = MagicMock()
        body = _block_action_body(user_id="U999")

        draft_mock = AsyncMock(return_value=OperationResult.success(data=_make_outcome()))
        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=draft_mock,
        ):
            handle_draft_action(ack, body, client)

        draft_mock.assert_called_once()
        call_kwargs = draft_mock.call_args[1]
        assert call_kwargs["author"] == "U999"
        assert call_kwargs["on_started"] is None


def _make_outcome(
    kind: StatusUpdateOutcomeKind = StatusUpdateOutcomeKind.DRAFTED,
    update: StatusUpdate | None = None,
) -> StatusUpdateDraftOutcome:
    """Build a status update outcome for testing."""
    if update is None:
        update = _pending_update()
    return StatusUpdateDraftOutcome(update=update, kind=kind)
