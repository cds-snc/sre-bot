"""Tests for the incident_draft Slack platform adapter."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog

from infrastructure.operations import OperationResult
from integrations.slack.models import CommandPayload
from packages.incident_draft.domain import DraftedDocument
from packages.incident_draft.platforms.slack import (
    _fetch_transcript,
    _find_incident_document_id,
    _resolve_limit,
    handle_draft_command,
    register_commands,
)
from packages.incident_draft.service import (
    DOCUMENT_UNREADABLE_CODE,
    EMPTY_HISTORY_CODE,
    NO_ANSWERS_CODE,
)
from packages.incident_draft.settings import IncidentDraftSettings

pytestmark = pytest.mark.unit

_DRAFT = "packages.incident_draft.platforms.slack.draft_incident_document"
_DOC_URL = "https://docs.google.com/document/d/DOC123/edit"


def _client(messages: list[dict] | None = None, bookmark_link: str = _DOC_URL) -> MagicMock:
    """Build a Slack client mock with a bookmarked incident doc and history."""
    client = MagicMock()
    client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {"title": "Some runbook", "link": "https://example.com"},
            {"title": "Incident report", "link": bookmark_link},
        ],
    }
    client.conversations_history.return_value = {"messages": messages or []}
    client.conversations_info.return_value = {"channel": {"created": 1_700_000_000}}
    client.users_info.return_value = {"ok": True, "user": {"profile": {"display_name": "Ada"}}}
    client.auth_test.return_value = {"ok": True, "user_id": "UBOT"}
    return client


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

        register_commands(provider)

        provider.register_command.assert_called_once()
        kwargs = provider.register_command.call_args.kwargs
        assert kwargs["command"] == "draft"
        assert kwargs["parent"] == "sre.incident"
        assert kwargs["fallback_handler"] is not None

    def test_fallback_dispatches_with_empty_args(self):
        provider = MagicMock()
        register_commands(provider)
        fallback = provider.register_command.call_args.kwargs["fallback_handler"]
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch("packages.incident_draft.platforms.slack.handle_draft_command") as mock_handle:
            fallback(payload)

        mock_handle.assert_called_once_with(payload, {}, provider.client)


class TestHandleDraftCommand:
    def test_success_is_a_single_line_linking_the_draft(self):
        client = _client([{"user": "U1", "text": "prod is down", "ts": "1"}])
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")
        outcome = _outcome(drafted=("Trigger", "Impact"), unanswered=("Lessons Learned",))

        with patch(_DRAFT, new=AsyncMock(return_value=OperationResult.success(data=outcome))) as mock_service:
            response = handle_draft_command(payload, {}, client)

        assert response.ephemeral is True
        assert response.message == (
            "Created an AI-generated <https://docs.google.com/document/d/NEW1/edit|draft incident report> "
            "from this channel. Copy over whatever's useful — all or part — into the original incident doc "
            "created when the incident opened."
        )
        # No per-section listing, however many sections were drafted or skipped.
        assert "•" not in response.message
        assert "\n" not in response.message
        # The source document is passed to the service; the draft is a new doc.
        assert mock_service.await_args.args[0] == "DOC123"

    def test_transcript_is_passed_to_the_service_chronologically(self):
        client = _client(
            [
                {"user": "U1", "text": "newest", "ts": "2"},
                {"user": "U1", "text": "oldest", "ts": "1"},
            ]
        )
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_DRAFT, new=AsyncMock(return_value=OperationResult.success(data=_outcome()))) as mock_service:
            handle_draft_command(payload, {}, client)

        messages = mock_service.await_args.args[1]
        assert [m.text for m in messages] == ["oldest", "newest"]

    def test_missing_bookmark_renders_notice_without_calling_service(self):
        client = _client()
        client.bookmarks_list.return_value = {"ok": True, "bookmarks": []}
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_DRAFT, new=AsyncMock()) as mock_service:
            response = handle_draft_command(payload, {}, client)

        assert "couldn't find an incident document" in response.message.lower()
        mock_service.assert_not_awaited()

    @pytest.mark.parametrize(
        ("error_code", "fragment"),
        [
            (DOCUMENT_UNREADABLE_CODE, "couldn't read any sections"),
            (EMPTY_HISTORY_CODE, "no channel history"),
            (NO_ANSWERS_CODE, "no draft was created"),
        ],
    )
    def test_known_error_codes_render_specific_notices(self, error_code, fragment):
        client = _client([{"user": "U1", "text": "hi", "ts": "1"}])
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(
            _DRAFT,
            new=AsyncMock(return_value=OperationResult.permanent_error(message="x", error_code=error_code)),
        ):
            response = handle_draft_command(payload, {}, client)

        assert response.ephemeral is True
        assert fragment in response.message.lower()

    def test_unknown_error_renders_generic_error(self):
        client = _client([{"user": "U1", "text": "hi", "ts": "1"}])
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(
            _DRAFT,
            new=AsyncMock(return_value=OperationResult.transient_error(message="boom", error_code="SERVER_ERROR")),
        ):
            response = handle_draft_command(payload, {}, client)

        assert response.message.startswith("❌")

    def test_missing_client_returns_error_without_calling_service(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_DRAFT, new=AsyncMock()) as mock_service:
            response = handle_draft_command(payload, {}, None)

        assert response.ephemeral is True
        mock_service.assert_not_awaited()

    def test_limit_argument_is_passed_to_history_fetch(self):
        client = _client([{"user": "U1", "text": "hi", "ts": "1"}])
        payload = CommandPayload(text="--limit 25", user_id="U9", channel_id="C123")

        with patch(_DRAFT, new=AsyncMock(return_value=OperationResult.success(data=_outcome()))):
            handle_draft_command(payload, {"--limit": 25}, client)

        assert client.conversations_history.call_args.kwargs["limit"] == 25


class TestFindIncidentDocumentId:
    def test_extracts_id_from_incident_report_bookmark(self):
        assert _find_incident_document_id(_client(), "C123", structlog.get_logger()) == "DOC123"

    def test_invalid_link_returns_none(self):
        client = _client(bookmark_link="https://example.com/not-a-doc")

        assert _find_incident_document_id(client, "C123", structlog.get_logger()) is None

    def test_api_error_returns_none(self):
        client = MagicMock()
        client.bookmarks_list.side_effect = RuntimeError("nope")

        assert _find_incident_document_id(client, "C123", structlog.get_logger()) is None


class TestHelpers:
    def test_fetch_transcript_resolves_display_names(self):
        client = _client([{"user": "U1", "text": "prod is down", "ts": "1"}])

        messages = _fetch_transcript(client, "C123", limit=10, oldest=0.0, log=structlog.get_logger())

        assert messages[0].author == "Ada"
        assert messages[0].text == "prod is down"

    def test_fetch_transcript_degrades_to_empty_on_api_error(self):
        client = _client()
        client.conversations_history.side_effect = RuntimeError("nope")

        assert _fetch_transcript(client, "C123", limit=10, oldest=0.0, log=structlog.get_logger()) == []

    def test_resolve_limit_caps_and_defaults(self):
        settings = IncidentDraftSettings(
            INCIDENT_DRAFT__DEFAULT_HISTORY_LIMIT=100,
            INCIDENT_DRAFT__MAX_HISTORY_LIMIT=200,
            INCIDENT_DRAFT__DEFAULT_SINCE_HOURS=24,
        )

        assert _resolve_limit(None, settings) == 100
        assert _resolve_limit("abc", settings) == 100
        assert _resolve_limit(-5, settings) == 100
        assert _resolve_limit(999, settings) == 200
        assert _resolve_limit(50, settings) == 50


class TestBotMessageFiltering:
    """The bot's own scaffolding messages must not reach the transcript."""

    def test_own_messages_are_excluded(self):
        client = _client(
            [
                {"user": "UBOT", "text": "A hangout has been created at: https://meet…", "ts": "3"},
                {"user": "UBOT", "text": "An incident report has been created at: …", "ts": "2"},
                {"user": "U1", "text": "prod is down", "ts": "1"},
            ]
        )

        messages = _fetch_transcript(client, "C123", limit=10, oldest=0.0, log=structlog.get_logger())

        assert [m.text for m in messages] == ["prod is down"]

    def test_other_bots_are_kept(self):
        """An alerting bot's message is often the first real timeline event."""
        client = _client(
            [
                {"user": "UPAGERDUTY", "text": "[ALERT] checkout 500 rate above threshold", "ts": "1"},
                {"user": "UBOT", "text": "An incident report has been created at: …", "ts": "2"},
            ]
        )

        messages = _fetch_transcript(client, "C123", limit=10, oldest=0.0, log=structlog.get_logger())

        assert [m.text for m in messages] == ["[ALERT] checkout 500 rate above threshold"]

    def test_auth_test_failure_keeps_every_message(self):
        """A failed self-lookup must degrade to no filtering, not an empty draft."""
        client = _client([{"user": "U1", "text": "prod is down", "ts": "1"}])
        client.auth_test.side_effect = RuntimeError("nope")

        messages = _fetch_transcript(client, "C123", limit=10, oldest=0.0, log=structlog.get_logger())

        assert [m.text for m in messages] == ["prod is down"]


class TestBotDetectionSignals:
    """Own-message detection must not rely on the user id alone."""

    def test_matches_on_bot_id_when_user_id_differs(self):
        client = _client(
            [
                {"user": "UOTHER", "bot_id": "BSELF", "text": "created a hangout", "ts": "2"},
                {"user": "U1", "text": "prod is down", "ts": "1"},
            ]
        )
        client.auth_test.return_value = {"ok": True, "user_id": "UBOT", "bot_id": "BSELF", "user": "sre_dev"}

        messages = _fetch_transcript(client, "C123", limit=10, oldest=0.0, log=structlog.get_logger())

        assert [m.text for m in messages] == ["prod is down"]

    def test_matches_on_display_name_when_ids_differ(self):
        """The case that slipped through: posted under an id auth_test doesn't report."""
        client = _client([{"user": "UUNKNOWN", "text": "posted a SEV-2 severity warning", "ts": "1"}])
        client.auth_test.return_value = {"ok": True, "user_id": "UBOT", "bot_id": "BSELF", "user": "sre_dev"}
        client.users_info.return_value = {"ok": True, "user": {"profile": {"display_name": "SRE Dev"}}}

        messages = _fetch_transcript(client, "C123", limit=10, oldest=0.0, log=structlog.get_logger())

        assert messages == []

    def test_channel_events_are_dropped_whoever_made_them(self):
        client = _client(
            [
                {"user": "U1", "subtype": "channel_topic", "text": "set the channel topic to: SEV-2", "ts": "3"},
                {"user": "U1", "subtype": "channel_join", "text": "has joined the channel", "ts": "2"},
                {"user": "U1", "text": "prod is down", "ts": "1"},
            ]
        )

        messages = _fetch_transcript(client, "C123", limit=10, oldest=0.0, log=structlog.get_logger())

        assert [m.text for m in messages] == ["prod is down"]

    def test_a_human_named_similarly_is_not_dropped(self):
        client = _client([{"user": "U1", "text": "prod is down", "ts": "1"}])
        client.auth_test.return_value = {"ok": True, "user_id": "UBOT", "bot_id": "BSELF", "user": "sre_dev"}
        client.users_info.return_value = {"ok": True, "user": {"profile": {"display_name": "Sam Devlin"}}}

        messages = _fetch_transcript(client, "C123", limit=10, oldest=0.0, log=structlog.get_logger())

        assert [m.text for m in messages] == ["prod is down"]


class TestProgressNotice:
    """The invoker is told work is underway, before the slow part starts."""

    def _run(self, client):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")
        with patch(_DRAFT, new=AsyncMock(return_value=OperationResult.success(data=_outcome()))):
            return handle_draft_command(payload, {}, client)

    def test_an_ephemeral_notice_is_posted_to_the_invoker(self):
        client = _client([{"user": "U1", "text": "prod is down", "ts": "1"}])

        self._run(client)

        client.chat_postEphemeral.assert_called_once()
        kwargs = client.chat_postEphemeral.call_args.kwargs
        assert kwargs["channel"] == "C123"
        assert kwargs["user"] == "U9"
        assert "drafting the incident report" in kwargs["text"]

    def test_the_notice_precedes_the_transcript_fetch(self):
        """Posting it after the slow work would defeat the point."""
        client = _client([{"user": "U1", "text": "prod is down", "ts": "1"}])
        order: list[str] = []
        client.chat_postEphemeral.side_effect = lambda **_: order.append("notice")
        client.conversations_history.side_effect = lambda **_: (order.append("history"), {"messages": []})[1]

        self._run(client)

        assert order[0] == "notice"

    def test_no_notice_when_the_channel_has_no_incident_document(self):
        """Nothing slow follows, so a progress note would only be noise."""
        client = _client()
        client.bookmarks_list.return_value = {"ok": True, "bookmarks": []}

        self._run(client)

        client.chat_postEphemeral.assert_not_called()

    def test_a_failed_notice_does_not_fail_the_command(self):
        client = _client([{"user": "U1", "text": "prod is down", "ts": "1"}])
        client.chat_postEphemeral.side_effect = RuntimeError("missing scope")

        response = self._run(client)

        assert "draft incident report" in response.message


class TestPartialDraftMessage:
    """A truncated run still produces a draft, and says what is missing."""

    def _run(self, partial: bool):
        client = _client([{"user": "U1", "text": "prod is down", "ts": "1"}])
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")
        outcome = DraftedDocument(
            document_id="NEW1",
            created=True,
            drafted_headings=("Trigger",),
            unanswered_headings=(),
            partial=partial,
        )
        with patch(_DRAFT, new=AsyncMock(return_value=OperationResult.success(data=outcome))):
            return handle_draft_command(payload, {}, client)

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


class TestTimestampFormatting:
    """Entries carry the date as well as the time — a clock alone is ambiguous."""

    @staticmethod
    def _stamp(tzname: str, ts: str = "1755450120") -> str:
        client = _client([{"user": "U1", "text": "prod is down", "ts": ts}])
        return _fetch_transcript(client, "C123", limit=10, oldest=0.0, log=structlog.get_logger(), tzname=tzname)[0].timestamp

    def test_slack_timestamps_carry_date_time_and_zone(self):
        stamp = self._stamp("America/Toronto")

        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} E[DS]T", stamp), stamp

    def test_the_zone_follows_daylight_saving(self):
        summer = self._stamp("America/Toronto", ts="1755450120")
        winter = self._stamp("America/Toronto", ts="1739450120")

        assert {summer.split()[-1], winter.split()[-1]} == {"EDT", "EST"}

    def test_an_unknown_zone_falls_back_to_utc(self):
        """A bad config value must not cost the timeline its timestamps."""
        assert self._stamp("Not/AZone") == self._stamp("UTC")

    def test_a_malformed_timestamp_yields_no_time(self):
        assert self._stamp("America/Toronto", ts="not-a-time") == ""
