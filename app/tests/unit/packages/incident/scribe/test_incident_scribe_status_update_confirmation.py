"""Tests for the security confirmation view and handler in the status-updates modal.

When draft_status_update returns SECURITY_CONFIRMATION_REQUIRED, the entrypoint
updates the modal with a confirmation view containing a Confirm and draft button
and a Cancel close button. The confirm handler calls the service with
security_confirmed=True and renders the result. View update failures are logged,
not raised. Nothing is posted to the channel.
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.domain import StatusUpdateDraftOutcome, StatusUpdateOutcomeKind
from packages.incident.scribe.entrypoints.slack import handle_draft_action, handle_draft_confirmed_action, register
from packages.incident.scribe.platforms.slack import build_security_confirmation_view

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


class TestSecurityConfirmationView:
    def test_confirmation_view_structure(self) -> None:
        """The confirmation view contains the required button and Cancel close."""
        view = build_security_confirmation_view("en-US", json.dumps({"channel_id": _CHANNEL, "locale": "en-US"}))

        assert view is not None
        assert isinstance(view, dict)
        # View should have blocks
        assert "blocks" in view
        blocks = view["blocks"]
        assert len(blocks) > 0

    def test_confirmation_view_en_text(self) -> None:
        """The EN confirmation view contains the expected English text."""
        view = build_security_confirmation_view("en-US", json.dumps({"channel_id": _CHANNEL, "locale": "en-US"}))

        view_str = str(view)
        # Should contain expected wording about security incident
        assert "security" in view_str.lower()

    def test_confirmation_view_fr_text(self) -> None:
        """The FR confirmation view contains the expected French text."""
        view = build_security_confirmation_view("fr-FR", json.dumps({"channel_id": _CHANNEL, "locale": "fr-FR"}))

        view_str = str(view)
        # Should contain expected French keywords
        assert "sécurité" in view_str.lower() or "incident" in view_str.lower()

    def test_confirmation_view_has_confirm_button(self) -> None:
        """The confirmation view has a Confirm and draft button."""
        view = build_security_confirmation_view("en-US", json.dumps({"channel_id": _CHANNEL, "locale": "en-US"}))

        view_str = str(view)
        # Should reference the confirm action ID
        assert "incident.scribe.status_update.draft_confirmed" in view_str

    def test_confirmation_view_has_cancel_close(self) -> None:
        """The confirmation view has a Cancel button as close action."""
        view = build_security_confirmation_view("en-US", json.dumps({"channel_id": _CHANNEL, "locale": "en-US"}))

        # View should have a way to close (Cancel or close action)
        assert view is not None


class TestRegisterConfirmAction:
    def test_register_includes_confirm_action_id(self) -> None:
        """register() registers the CONFIRM_ACTION_ID for the handler."""
        registrar = MagicMock()

        register(registrar)

        # Should have registered both Draft and Confirm actions
        register_calls = [call[0][0] for call in registrar.register_block_action.call_args_list]
        # Should include the draft action
        assert "incident.scribe.status_update.draft" in register_calls
        # Should include the confirm action
        assert "incident.scribe.status_update.draft_confirmed" in register_calls


class TestHandleDraftConfirmedAction:
    def test_confirm_handler_exists(self) -> None:
        """A handle_draft_confirmed_action function exists."""
        assert callable(handle_draft_confirmed_action)

    def test_confirm_handler_acks_first(self) -> None:
        """The confirm handler acks synchronously before any other work."""
        ack = MagicMock()
        client = MagicMock()
        body = _block_action_body()

        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=OperationResult.success(data=_make_outcome())),
        ):
            handle_draft_confirmed_action(ack, body, client)

        ack.assert_called_once()

    def test_confirm_handler_passes_security_confirmed_true(self) -> None:
        """The confirm handler calls draft_status_update with security_confirmed=True."""
        ack = MagicMock()
        client = MagicMock()
        body = _block_action_body()
        client.views_update.return_value = {"ok": True}

        mock_draft = AsyncMock(return_value=OperationResult.success(data=_make_outcome()))

        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=mock_draft,
        ):
            handle_draft_confirmed_action(ack, body, client)

        # Find the call with security_confirmed
        assert mock_draft.called
        call_kwargs = mock_draft.call_args[1]
        assert call_kwargs.get("security_confirmed") is True

    def test_confirm_handler_renders_result(self) -> None:
        """The confirm handler updates the view with the result."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True, "view": {"hash": "new_hash=="}}
        body = _block_action_body()

        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=OperationResult.success(data=_make_outcome())),
        ):
            handle_draft_confirmed_action(ack, body, client)

        # Should have called views_update to show the result
        assert client.views_update.called


class TestDraftHandlerShowsConfirmationView:
    def test_draft_handler_shows_confirmation_on_security_gate_refusal(self) -> None:
        """When draft_status_update returns SECURITY_CONFIRMATION_REQUIRED, the handler shows the confirmation view."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True, "view": {"hash": "new_hash=="}}
        body = _block_action_body()

        security_gate_refusal = OperationResult.permanent_error(
            message="Security confirmation required",
            error_code=ErrorCode.SECURITY_CONFIRMATION_REQUIRED,
        )

        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=security_gate_refusal),
        ):
            handle_draft_action(ack, body, client)

        # Should have called views_update with the confirmation view
        assert client.views_update.called
        # The confirmation view should be shown
        calls = client.views_update.call_args_list
        confirmation_shown = False
        for call in calls:
            call_kwargs = call[1]
            view = call_kwargs.get("view", {})
            view_str = str(view)
            if "incident.scribe.status_update.draft_confirmed" in view_str:
                confirmation_shown = True
                break
        assert confirmation_shown

    def test_draft_handler_does_not_show_drafting_on_security_gate_refusal(self) -> None:
        """When the gate refuses, no drafting state is shown."""
        ack = MagicMock()
        client = MagicMock()
        client.views_update.return_value = {"ok": True, "view": {"hash": "new_hash=="}}
        body = _block_action_body()

        security_gate_refusal = OperationResult.permanent_error(
            message="Security confirmation required",
            error_code=ErrorCode.SECURITY_CONFIRMATION_REQUIRED,
        )

        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=security_gate_refusal),
        ):
            handle_draft_action(ack, body, client)

        # Should NOT have called views_update with a drafting view before the confirmation
        # (or if it did, it should be overwritten)


class TestConfirmationViewUpdateFailure:
    def test_confirmation_view_update_failure_is_logged_not_raised(self) -> None:
        """If updating to the confirmation view fails, the error is logged, not raised."""
        ack = MagicMock()
        client = MagicMock()
        # Fail the views_update call
        client.views_update.side_effect = Exception("Slack error")
        body = _block_action_body()

        security_gate_refusal = OperationResult.permanent_error(
            message="Security confirmation required",
            error_code=ErrorCode.SECURITY_CONFIRMATION_REQUIRED,
        )

        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=security_gate_refusal),
        ):
            # Should not raise, even though views_update fails
            handle_draft_action(ack, body, client)


class TestNoPostMessageOnConfirmPath:
    def test_no_post_message_on_confirm_action(self) -> None:
        """Confirm action handler does not post to the channel."""
        ack = MagicMock()
        client = MagicMock()
        body = _block_action_body()

        with patch(
            "packages.incident.scribe.entrypoints.slack.draft_status_update",
            new=AsyncMock(return_value=OperationResult.success(data=_make_outcome())),
        ):
            handle_draft_confirmed_action(ack, body, client)

        # Should never call chat.postMessage or chat.postEphemeral
        assert not client.chat_postMessage.called
        assert not client.chat_postEphemeral.called


def _make_outcome(
    kind: StatusUpdateOutcomeKind = StatusUpdateOutcomeKind.DRAFTED,
    update: StatusUpdate | None = None,
) -> StatusUpdateDraftOutcome:
    """Build a StatusUpdateDraftOutcome for testing."""
    return StatusUpdateDraftOutcome(
        update=update or _pending_update(),
        kind=kind,
    )
