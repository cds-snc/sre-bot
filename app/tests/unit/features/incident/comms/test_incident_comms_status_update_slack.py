"""Tests for the incident comms Slack platform adapter: the status-update command and handler shape.

The command opens a loading view first with the command's trigger id, then resolves
the incident, reads the pending draft and updates the view to it rendered with the
default comms profile in EN and FR, or to a localized error view. Every
status-update handler makes one service call and builds no domain value itself.
"""

import ast
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from contracts.slack.models import CommandPayload
from contracts.workplace import WorkplaceSystem
from features.incident.comms.domain import StatusUpdateOverview
from features.incident.comms.entrypoints import slack as slack_entrypoints
from features.incident.comms.entrypoints.slack import handle_status_update_command, register
from features.incident.comms.entrypoints.slack_views import (
    GENERATE_ACTION_ID,
    HISTORY_ACTION_ID,
    NEW_ACTION_ID,
    OPEN_ACTION_ID,
    PUBLISHED_ACTION_ID,
    REVIEW_ACTION_ID,
    REVIEW_CALLBACK_ID,
    SAVE_ACTION_ID,
)
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from tests.factories.incident import incident_scopes
from tests.factories.slack import FakeSlackRegistrar, FakeSlackReply

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_TRIGGER = "trigger-abc-123"


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
        author="U123",
        transcript_cutoff=now,
        transcript_fingerprint="v1:sha256:abc123",
        created_at=now,
    )


class TestRegisterCommands:
    def test_registers_status_update_under_sre_incident(self):
        registrar = FakeSlackRegistrar(service_scopes=incident_scopes())

        register(registrar)

        status_update_calls = [kwargs for kwargs in registrar.commands if kwargs.get("command") == "status-update"]
        assert len(status_update_calls) == 1
        assert status_update_calls[0]["parent"] == "sre.incident"

    def test_registers_every_listener_when_slack_is_configured(self):
        registrar = FakeSlackRegistrar(service_scopes=incident_scopes())

        with capture_logs() as logs:
            register(registrar)

        assert set(registrar.block_actions) == {
            NEW_ACTION_ID,
            SAVE_ACTION_ID,
            GENERATE_ACTION_ID,
            REVIEW_ACTION_ID,
            OPEN_ACTION_ID,
            HISTORY_ACTION_ID,
            PUBLISHED_ACTION_ID,
        }
        assert set(registrar.view_submissions) == {REVIEW_CALLBACK_ID}
        assert not [log for log in logs if log["event"] == "incident_comms_registration_skipped"]

    def test_registers_nothing_and_names_the_setting_once_when_slack_is_not_configured(self):
        """Without a Slack tenant no incident can be resolved, so the commands are skipped at startup."""
        scopes = incident_scopes(tenants={WorkplaceSystem.GOOGLE: "C0GOOGLE"})
        registrar = FakeSlackRegistrar(service_scopes=scopes)

        with capture_logs() as logs:
            register(registrar)

        assert registrar.commands == []
        assert registrar.block_actions == {}
        assert registrar.view_submissions == {}
        skipped = [log for log in logs if log["event"] == "incident_comms_registration_skipped"]
        assert len(skipped) == 1
        assert skipped[0]["setting"] == "[slack.tenant] team_id"
        assert (scopes.opened, scopes.closed) == (1, 1)


class TestHandleStatusUpdateCommand:
    def test_opens_loading_view_before_any_lookup(self):
        """The loading view is opened first with the trigger id, before any business logic."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})
        reply = FakeSlackReply()

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(
                return_value=OperationResult.success(data=StatusUpdateOverview(pending=_pending_update(), approved=()))
            ),
        ):
            handle_status_update_command(payload, {}, reply, incident_scopes())

        open_calls = reply.calls_to("open_view")
        assert len(open_calls) >= 1
        assert open_calls[0]["trigger_id"] == _TRIGGER

    def test_updates_view_with_pending_draft_in_en_and_fr(self):
        """When a draft exists, the view is updated to show the pending status in EN and FR sections."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})
        reply = FakeSlackReply(OperationResult.success(data="view-id-123"))

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(
                return_value=OperationResult.success(data=StatusUpdateOverview(pending=_pending_update(), approved=()))
            ),
        ):
            handle_status_update_command(payload, {}, reply, incident_scopes())

        update_calls = reply.calls_to("update_view")
        assert len(update_calls) >= 1
        # The view should contain both EN and FR sections
        view = update_calls[0]["view"]
        sections = [block["text"]["text"] for block in view["blocks"] if block["type"] == "section"]
        assert sections[0] == (
            "Stage: Identified\n"
            "Affected service: en service\n"
            "Impact: en impact\n"
            "Current action: en action\n"
            "Workaround: en workaround\n"
            "Next update: 2026-10-07 11:00 ET"
        )

    def test_shows_no_pending_view_when_no_draft_exists(self):
        """When no draft exists, the view is updated to show a no-pending message."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})
        reply = FakeSlackReply(OperationResult.success(data="view-id-123"))

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(return_value=OperationResult.success(data=StatusUpdateOverview(pending=None, approved=()))),
        ):
            handle_status_update_command(payload, {}, reply, incident_scopes())

        update_calls = reply.calls_to("update_view")
        assert len(update_calls) >= 1

    def test_refuses_with_error_when_no_trigger_id(self):
        """When the command has no trigger_id, an error is returned and no view is opened."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL)
        reply = FakeSlackReply()

        response = handle_status_update_command(payload, {}, reply, incident_scopes())

        assert response.ephemeral is True
        assert reply.calls_to("open_view") == []

    def test_updates_view_with_error_when_not_an_incident_channel(self):
        """Outside an incident channel, the view is updated to show a localized refusal with a Close button."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})
        reply = FakeSlackReply(OperationResult.success(data="view-id-123"))

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(
                return_value=OperationResult.error(
                    OperationStatus.NOT_FOUND,
                    message="no incident",
                    error_code=ErrorCode.NOT_AN_INCIDENT,
                )
            ),
        ):
            handle_status_update_command(payload, {}, reply, incident_scopes())

        # The view should be updated to the error state
        update_calls = reply.calls_to("update_view")
        assert len(update_calls) >= 1

    def test_updates_view_with_error_when_ambiguous_incident(self):
        """When the conversation maps to multiple incidents, an error view is shown."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})
        reply = FakeSlackReply(OperationResult.success(data="view-id-123"))

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(
                return_value=OperationResult.permanent_error(
                    message="multiple incidents",
                    error_code=ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION,
                )
            ),
        ):
            handle_status_update_command(payload, {}, reply, incident_scopes())

        update_calls = reply.calls_to("update_view")
        assert len(update_calls) >= 1

    def test_updates_view_with_error_on_store_failure(self):
        """When the store fails, an error view is shown."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})
        reply = FakeSlackReply(OperationResult.success(data="view-id-123"))

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(
                return_value=OperationResult.transient_error(
                    message="throttled",
                    error_code=ErrorCode.RATE_LIMITED,
                    retry_after=3,
                )
            ),
        ):
            handle_status_update_command(payload, {}, reply, incident_scopes())

        update_calls = reply.calls_to("update_view")
        assert len(update_calls) >= 1

    def test_returns_ephemeral_error_when_open_view_fails(self):
        """When opening the view fails, an ephemeral error is returned since no view exists to update."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})
        reply = FakeSlackReply(
            OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="expired trigger",
                error_code="expired_trigger_id",
            )
        )

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(
                return_value=OperationResult.success(data=StatusUpdateOverview(pending=_pending_update(), approved=()))
            ),
        ):
            response = handle_status_update_command(payload, {}, reply, incident_scopes())

        # Should return an ephemeral error since we can't open the view
        assert response.ephemeral is True

    def test_logs_when_update_view_fails(self):
        """When updating the view fails, the error is logged and the loading view is left."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})

        class _FailOnUpdateReply(FakeSlackReply):
            """Opens the view, then fails every update as Slack does for an invalid view."""

            def update_view(self, *, view_id: str, view: dict[str, Any], hash: str | None = None) -> OperationResult[None]:
                self.calls.append(("update_view", {"view_id": view_id, "view": view, "hash": hash}))
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message="not a valid view",
                    error_code="invalid_view",
                )

        reply = _FailOnUpdateReply(OperationResult.success(data="view-id-123"))

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(
                return_value=OperationResult.success(data=StatusUpdateOverview(pending=_pending_update(), approved=()))
            ),
        ):
            handle_status_update_command(payload, {}, reply, incident_scopes())

        # Both open and update should have been called
        assert len(reply.calls_to("open_view")) >= 1
        assert len(reply.calls_to("update_view")) >= 1

    def test_makes_no_post_message_or_post_ephemeral_calls(self):
        """The status-update command only opens and updates views, never posts to the channel or as ephemeral."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})
        reply = FakeSlackReply(OperationResult.success(data="view-id-123"))

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(
                return_value=OperationResult.success(data=StatusUpdateOverview(pending=_pending_update(), approved=()))
            ),
        ):
            handle_status_update_command(payload, {}, reply, incident_scopes())

        assert len(reply.calls_to("post_message")) == 0
        assert len(reply.calls_to("post_ephemeral")) == 0


class TestOverviewButtonsInViews:
    """The status-updates modal offers Review for a pending draft and New update without one, never Draft."""

    def test_review_button_alone_in_pending_view(self):
        """The pending draft view's actions block holds only the Review button."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})
        reply = FakeSlackReply(OperationResult.success(data="view-id-123"))

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(
                return_value=OperationResult.success(data=StatusUpdateOverview(pending=_pending_update(), approved=()))
            ),
        ):
            handle_status_update_command(payload, {}, reply, incident_scopes())

        update_calls = reply.calls_to("update_view")
        assert len(update_calls) >= 1
        view = update_calls[0]["view"]
        (actions,) = [block for block in view["blocks"] if block.get("block_id") == "overview_actions"]
        assert [element["action_id"] for element in actions["elements"]] == [REVIEW_ACTION_ID]

    def test_new_update_button_alone_in_no_pending_view(self):
        """The no-pending view's actions block holds only the New update button."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})
        reply = FakeSlackReply(OperationResult.success(data="view-id-123"))

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(return_value=OperationResult.success(data=StatusUpdateOverview(pending=None, approved=()))),
        ):
            handle_status_update_command(payload, {}, reply, incident_scopes())

        update_calls = reply.calls_to("update_view")
        assert len(update_calls) >= 1
        view = update_calls[0]["view"]
        (actions,) = [block for block in view["blocks"] if block.get("block_id") == "overview_actions"]
        assert [element["action_id"] for element in actions["elements"]] == [NEW_ACTION_ID]

    def test_overview_buttons_absent_in_error_view(self):
        """Error views (not-an-incident, ambiguous, etc.) have no overview actions block."""
        payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": _TRIGGER})
        reply = FakeSlackReply(OperationResult.success(data="view-id-123"))

        with patch(
            "features.incident.comms.entrypoints.slack.get_status_update_overview",
            new=MagicMock(
                return_value=OperationResult.error(
                    OperationStatus.NOT_FOUND,
                    message="no incident",
                    error_code=ErrorCode.NOT_AN_INCIDENT,
                )
            ),
        ):
            handle_status_update_command(payload, {}, reply, incident_scopes())

        update_calls = reply.calls_to("update_view")
        assert len(update_calls) >= 1
        view = update_calls[0]["view"]
        assert [block for block in view["blocks"] if block.get("block_id") == "overview_actions"] == []


_STATUS_UPDATE_HANDLERS = (
    "handle_status_update_command",
    "handle_new_update_action",
    "handle_review_action",
    "handle_open_action",
    "handle_history_action",
    "handle_published_action",
    "handle_generate_action",
    "handle_save_action",
    "handle_review_submission",
)
# "About 30 lines": a long keyword-argument call laid out one argument per line counts each line.
_MAX_HANDLER_LINES = 35
_SERVICE_MODULES = frozenset(f"features.incident.comms.{name}" for name in ("approval", "form", "history", "service"))


def _entrypoint_tree() -> ast.Module:
    return ast.parse(Path(slack_entrypoints.__file__).read_text())


def _service_names(tree: ast.Module) -> set[str]:
    """Names the entry point imports from the status-update service modules."""
    return {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module in _SERVICE_MODULES
        for alias in node.names
    }


class TestHandlerDiscipline:
    """The status-update handlers receive, parse, make one service call and render.

    The entry point's source is parsed, so the checks hold for every handler
    without running it: the body's length (docstring excluded), the calls to
    names imported from the status-update service modules, and ``asyncio.run``.
    """

    @pytest.mark.parametrize("name", _STATUS_UPDATE_HANDLERS)
    def test_handler_makes_one_service_call_in_at_most_one_event_loop(self, name: str) -> None:
        tree = _entrypoint_tree()
        services = _service_names(tree)
        handler = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
        calls = [node for node in ast.walk(handler) if isinstance(node, ast.Call)]

        service_calls = [call for call in calls if isinstance(call.func, ast.Name) and call.func.id in services]
        event_loops = [call for call in calls if ast.unparse(call.func) == "asyncio.run"]
        body = handler.body[1:] if ast.get_docstring(handler) else handler.body
        lines = (body[-1].end_lineno or 0) - body[0].lineno + 1

        assert len(service_calls) == 1
        assert len(event_loops) <= 1
        assert lines <= _MAX_HANDLER_LINES

    def test_entry_point_imports_no_domain_constructor_or_replace(self) -> None:
        """Kept drafts are built by the service, so the entry point needs neither the domain types nor ``replace``."""
        tree = _entrypoint_tree()
        imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)]

        assert not [node for node in imports if node.module == "features.incident.comms.domain"]
        assert not [node for node in imports if node.module == "dataclasses" and any(a.name == "replace" for a in node.names)]
