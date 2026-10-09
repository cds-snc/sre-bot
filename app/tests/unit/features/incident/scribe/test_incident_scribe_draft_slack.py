"""Tests for the incident scribe Slack platform adapter: the draft command."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contracts.operations import OperationResult, OperationStatus
from contracts.slack.models import CommandPayload
from features.incident.scribe.domain import DraftedDocument
from features.incident.scribe.entrypoints.slack import handle_draft_command, register
from features.incident.scribe.service import (
    DOCUMENT_UNREADABLE_CODE,
    EMPTY_HISTORY_CODE,
    NO_ANSWERS_CODE,
    NO_DOCUMENT_CODE,
)
from tests.factories.slack import FakeSlackReply

pytestmark = pytest.mark.unit

_DRAFT = "features.incident.scribe.entrypoints.slack.draft_incident_document_from_conversation"


def _service(result: OperationResult[DraftedDocument], *, signal_start: bool = True) -> AsyncMock:
    """Stub the service call: signal the start as the service does once the report is found, then return ``result``."""

    async def _call(
        conversation_id: str, *, limit: int | None = None, on_started: Callable[[], None] | None = None
    ) -> OperationResult[DraftedDocument]:
        if signal_start and on_started is not None:
            on_started()
        return result

    return AsyncMock(side_effect=_call)


def _draft_registration(provider: MagicMock) -> dict:
    """Return the keyword arguments of the ``draft`` command's registration."""
    (kwargs,) = [call.kwargs for call in provider.register_command.call_args_list if call.kwargs["command"] == "draft"]
    return kwargs


def _outcome(document_id: str = "NEW1", drafted=("Trigger",), unanswered=(), created: bool = True) -> DraftedDocument:
    return DraftedDocument(
        document_id=document_id,
        created=created,
        drafted_headings=tuple(drafted),
        unanswered_headings=tuple(unanswered),
    )


class TestRegisterCommands:
    def test_registers_draft_under_sre_incident(self):
        provider = MagicMock()

        register(provider)

        kwargs = _draft_registration(provider)
        assert kwargs["command"] == "draft"
        assert kwargs["parent"] == "sre.incident"
        assert kwargs["fallback_handler"] is not None

    def test_fallback_dispatches_with_empty_args(self):
        provider = MagicMock()
        register(provider)
        fallback = _draft_registration(provider)["fallback_handler"]
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch("features.incident.scribe.entrypoints.slack.handle_draft_command") as mock_handle:
            fallback(payload)

        mock_handle.assert_called_once_with(payload, {}, provider.reply)


class TestHandleDraftCommand:
    def test_success_is_a_single_line_linking_the_draft(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")
        outcome = _outcome(drafted=("Trigger", "Impact"), unanswered=("Lessons Learned",))

        with patch(_DRAFT, new=_service(OperationResult.success(data=outcome))) as mock_service:
            response = handle_draft_command(payload, {}, FakeSlackReply())

        assert response.ephemeral is True
        assert response.message == (
            "Created an AI-generated <https://docs.google.com/document/d/NEW1/edit|draft incident report> "
            "from this channel. Copy over whatever's useful — all or part — into the original incident doc "
            "created when the incident opened."
        )
        # No per-section listing, however many sections were drafted or skipped.
        assert "•" not in response.message
        assert "\n" not in response.message
        # One service call, for the channel the command was run in.
        mock_service.assert_awaited_once()
        assert mock_service.await_args.args == ("C123",)

    def test_no_document_renders_the_notice(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")
        result: OperationResult[DraftedDocument] = OperationResult.permanent_error(message="x", error_code=NO_DOCUMENT_CODE)

        with patch(_DRAFT, new=_service(result, signal_start=False)):
            response = handle_draft_command(payload, {}, FakeSlackReply())

        assert response.ephemeral is True
        assert response.message == "I couldn't find an incident document bookmarked in this channel."

    @pytest.mark.parametrize(
        ("error_code", "fragment"),
        [
            (DOCUMENT_UNREADABLE_CODE, "couldn't read any sections"),
            (EMPTY_HISTORY_CODE, "no channel history"),
            (NO_ANSWERS_CODE, "no draft was created"),
        ],
    )
    def test_known_error_codes_render_specific_notices(self, error_code, fragment):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_DRAFT, new=_service(OperationResult.permanent_error(message="x", error_code=error_code))):
            response = handle_draft_command(payload, {}, FakeSlackReply())

        assert response.ephemeral is True
        assert fragment in response.message.lower()

    def test_unknown_error_renders_generic_error(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_DRAFT, new=_service(OperationResult.transient_error(message="boom", error_code="SERVER_ERROR"))):
            response = handle_draft_command(payload, {}, FakeSlackReply())

        assert response.message.startswith("❌")

    def test_missing_channel_id_returns_error_without_calling_service(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="")
        reply = FakeSlackReply()

        with patch(_DRAFT, new=AsyncMock()) as mock_service:
            response = handle_draft_command(payload, {}, reply)

        assert response.ephemeral is True
        assert response.message.startswith("\u274c")
        mock_service.assert_not_awaited()
        assert reply.calls == []

    @pytest.mark.parametrize(
        ("parsed_args", "expected"),
        [({"--limit": 25}, 25), ({"--limit": "25"}, 25), ({"--limit": "abc"}, None), ({}, None)],
    )
    def test_limit_argument_is_passed_to_the_service(self, parsed_args, expected):
        """A readable ``--limit`` reaches the service as an integer; absent or unreadable means the service default."""
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_DRAFT, new=_service(OperationResult.success(data=_outcome()))) as mock_service:
            handle_draft_command(payload, parsed_args, FakeSlackReply())

        assert mock_service.await_args.kwargs["limit"] == expected


class TestProgressNotice:
    """The invoker is told work is underway, when the service signals the slow part is starting."""

    def _run(self, reply, *, signal_start: bool = True):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")
        with patch(_DRAFT, new=_service(OperationResult.success(data=_outcome()), signal_start=signal_start)):
            return handle_draft_command(payload, {}, reply)

    def test_an_ephemeral_notice_is_posted_to_the_invoker(self):
        reply = FakeSlackReply()

        self._run(reply)

        (kwargs,) = reply.calls_to("post_ephemeral")
        assert kwargs["channel_id"] == "C123"
        assert kwargs["user_id"] == "U9"
        assert "drafting the incident report" in kwargs["text"]

    def test_no_notice_until_the_service_signals_the_start(self):
        """The handler posts nothing on its own: when to post is the service's call."""
        reply = FakeSlackReply()

        self._run(reply, signal_start=False)

        assert reply.calls == []

    def test_a_failed_notice_does_not_fail_the_command(self):
        reply = FakeSlackReply(OperationResult.error(OperationStatus.UNAUTHORIZED, "missing scope", error_code="missing_scope"))

        response = self._run(reply)

        assert "draft incident report" in response.message


class TestPartialDraftMessage:
    """A truncated run still produces a draft, and says what is missing."""

    def _run(self, partial: bool):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")
        outcome = DraftedDocument(
            document_id="NEW1",
            created=True,
            drafted_headings=("Trigger",),
            unanswered_headings=(),
            partial=partial,
        )
        with patch(_DRAFT, new=_service(OperationResult.success(data=outcome))):
            return handle_draft_command(payload, {}, FakeSlackReply())

    def test_a_partial_run_links_the_draft_and_explains_the_gap(self):
        response = self._run(partial=True)

        assert "https://docs.google.com/document/d/NEW1/edit" in response.message
        assert "later sections are missing" in response.message
        assert "re-run" in response.message
        # Not an error: a usable draft exists.
        assert not response.message.startswith("⚠")

    def test_a_complete_run_says_nothing_about_missing_sections(self):
        response = self._run(partial=False)

        assert "later sections are missing" not in response.message
