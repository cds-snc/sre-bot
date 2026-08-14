"""Tests for the incident_summary Slack platform adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog

from infrastructure.operations import OperationResult
from integrations.slack.models import CommandPayload
from packages.incident_summary.platforms.slack import (
    _fetch_transcript,
    _parse_since_seconds,
    _resolve_channel_start,
    _resolve_display_name,
    _resolve_limit,
    _resolve_oldest,
    _to_slack_mrkdwn,
    handle_summarize_command,
    register_commands,
)
from packages.incident_summary.service import EMPTY_HISTORY_CODE
from packages.incident_summary.settings import IncidentSummarySettings

pytestmark = pytest.mark.unit

_SUMMARIZE = "packages.incident_summary.platforms.slack.summarize_transcript"


def _client_with_history(messages: list[dict], display_name: str = "Ada") -> MagicMock:
    """Build a Slack client mock for conversations_history + users_info."""
    client = MagicMock()
    client.conversations_history.return_value = {"messages": messages}
    client.conversations_info.return_value = {"channel": {"created": 1_700_000_000}}
    client.users_info.return_value = {
        "ok": True,
        "user": {"profile": {"display_name": display_name}},
    }
    return client


class TestRegisterCommands:
    def test_registers_summarize_under_sre_incident(self):
        provider = MagicMock()

        register_commands(provider)

        provider.register_command.assert_called_once()
        kwargs = provider.register_command.call_args.kwargs
        assert kwargs["command"] == "summarize"
        assert kwargs["parent"] == "sre.incident"
        assert kwargs["fallback_handler"] is not None
        assert kwargs["handler"] is not None

    def test_handler_dispatches_with_provider_client_and_parsed_args(self):
        provider = MagicMock()
        register_commands(provider)
        handler = provider.register_command.call_args.kwargs["handler"]
        payload = CommandPayload(text="--limit 5", user_id="U9", channel_id="C123")

        target = "packages.incident_summary.platforms.slack.handle_summarize_command"
        with patch(target) as mock_handle:
            handler(payload, {"--limit": 5})

        mock_handle.assert_called_once_with(payload, {"--limit": 5}, provider.client)

    def test_fallback_dispatches_with_empty_args(self):
        provider = MagicMock()
        register_commands(provider)
        fallback = provider.register_command.call_args.kwargs["fallback_handler"]
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        target = "packages.incident_summary.platforms.slack.handle_summarize_command"
        with patch(target) as mock_handle:
            fallback(payload)

        mock_handle.assert_called_once_with(payload, {}, provider.client)


class TestHandleSummarizeCommand:
    def test_success_renders_ephemeral_summary(self):
        client = _client_with_history([{"user": "U1", "text": "prod is down", "ts": "1"}])
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="Everything is on fire"))) as mock_service:
            response = handle_summarize_command(payload, {}, client)

        assert response.ephemeral is True
        assert "Everything is on fire" in response.message
        mock_service.assert_awaited_once()

    def test_empty_history_renders_localized_notice(self):
        client = _client_with_history([])
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(
            _SUMMARIZE,
            new=AsyncMock(return_value=OperationResult.permanent_error(message="nothing", error_code=EMPTY_HISTORY_CODE)),
        ):
            response = handle_summarize_command(payload, {}, client)

        assert response.ephemeral is True
        assert "nothing to summarize" in response.message.lower()

    def test_summarizer_error_renders_generic_error(self):
        client = _client_with_history([{"user": "U1", "text": "prod is down", "ts": "1"}])
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(
            _SUMMARIZE, new=AsyncMock(return_value=OperationResult.transient_error(message="boom", error_code="SERVER_ERROR"))
        ):
            response = handle_summarize_command(payload, {}, client)

        assert response.ephemeral is True
        assert response.message.startswith("❌")
        assert "nothing to summarize" not in response.message.lower()

    def test_missing_client_returns_error_without_calling_service(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock()) as mock_service:
            response = handle_summarize_command(payload, {}, None)

        assert response.ephemeral is True
        mock_service.assert_not_awaited()

    def test_missing_channel_id_returns_error_without_calling_service(self):
        client = _client_with_history([{"user": "U1", "text": "hi", "ts": "1"}])
        payload = CommandPayload(text="", user_id="U9", channel_id="")

        with patch(_SUMMARIZE, new=AsyncMock()) as mock_service:
            response = handle_summarize_command(payload, {}, client)

        assert response.ephemeral is True
        assert response.message.startswith("\u274c")
        mock_service.assert_not_awaited()
        client.conversations_history.assert_not_called()

    def test_success_message_includes_header(self):
        client = _client_with_history([{"user": "U1", "text": "prod is down", "ts": "1"}])
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="the summary body"))):
            response = handle_summarize_command(payload, {}, client)

        # Header precedes the summary body, separated by a blank line.
        assert response.message.endswith("the summary body")
        assert response.message.split("\n\n", 1)[0].strip() != ""
        assert response.message != "the summary body"

    def test_summary_body_is_normalized_to_slack_mrkdwn(self):
        client = _client_with_history([{"user": "U1", "text": "prod is down", "ts": "1"}])
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")
        raw = "## **Key events**\n- • first\n- second"

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data=raw))):
            response = handle_summarize_command(payload, {}, client)

        assert "**" not in response.message
        assert "##" not in response.message
        assert "\u2022 \u2022" not in response.message
        assert "*Key events*" in response.message

    def test_limit_argument_is_passed_to_history_fetch(self):
        client = _client_with_history([{"user": "U1", "text": "hi", "ts": "1"}])
        payload = CommandPayload(text="--limit 25", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="ok"))):
            handle_summarize_command(payload, {"--limit": 25}, client)

        assert client.conversations_history.call_args.kwargs["limit"] == 25
        # oldest must be a Slack "seconds.6digits" timestamp, not a raw float
        # repr (a 7+ decimal value silently matches nothing and returns zero
        # messages).
        oldest = client.conversations_history.call_args.kwargs["oldest"]
        assert isinstance(oldest, str)
        assert len(oldest.rsplit(".", 1)[1]) == 6

    def test_since_argument_sets_oldest_window(self):
        import time

        client = _client_with_history([{"user": "U1", "text": "hi", "ts": "1"}])
        payload = CommandPayload(text="--since 2h", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="ok"))):
            handle_summarize_command(payload, {"--since": "2h"}, client)

        oldest = float(client.conversations_history.call_args.kwargs["oldest"])
        # 2 hours ago, within a small tolerance for execution time.
        assert abs((time.time() - 2 * 3600) - oldest) < 5

    def test_default_window_starts_at_channel_creation(self):
        client = _client_with_history([{"user": "U1", "text": "hi", "ts": "1"}])
        client.conversations_info.return_value = {"channel": {"created": 1_700_000_000}}
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="ok"))):
            handle_summarize_command(payload, {}, client)

        client.conversations_info.assert_called_once_with(channel="C123")
        oldest = float(client.conversations_history.call_args.kwargs["oldest"])
        assert oldest == 1_700_000_000.0

    def test_slack_mrkdwn_instructions_passed_to_service(self):
        client = _client_with_history([{"user": "U1", "text": "hi", "ts": "1"}])
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="ok"))) as mock_service:
            handle_summarize_command(payload, {}, client)

        instructions = mock_service.await_args.kwargs["instructions"]
        assert "mrkdwn" in instructions.lower()

    def test_bot_and_empty_messages_are_filtered_out(self):
        # Only human messages with both text and a user survive; bot messages
        # (no ``user``) and empty-text messages are dropped.
        client = _client_with_history(
            [
                {"user": "U1", "text": "real message", "ts": "3"},
                {"bot_id": "B1", "text": "posted by an app", "ts": "2"},
                {"user": "U1", "text": "   ", "ts": "1"},
            ]
        )
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="ok"))) as mock_service:
            handle_summarize_command(payload, {}, client)

        messages = mock_service.await_args.args[0]
        assert [m.text for m in messages] == ["real message"]

    def test_history_fetch_error_renders_empty_history(self):
        client = MagicMock()
        client.conversations_history.side_effect = RuntimeError("slack exploded")
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(
            _SUMMARIZE,
            new=AsyncMock(return_value=OperationResult.permanent_error(message="nothing", error_code=EMPTY_HISTORY_CODE)),
        ) as mock_service:
            response = handle_summarize_command(payload, {}, client)

        # A Slack API failure degrades to an empty transcript, so the service
        # is called with no messages and the empty-history notice is shown.
        assert mock_service.await_args.args[0] == []
        assert response.ephemeral is True
        assert "nothing to summarize" in response.message.lower()

    def test_history_is_built_chronologically_with_resolved_names(self):
        # conversations_history returns newest-first; the service must receive
        # chronological "author: text" lines with display names resolved.
        client = _client_with_history(
            [
                {"user": "U1", "text": "second", "ts": "2"},
                {"user": "U1", "text": "first", "ts": "1"},
            ],
            display_name="Ada",
        )
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="ok"))) as mock_service:
            handle_summarize_command(payload, {}, client)

        messages = mock_service.await_args.args[0]
        assert [m.text for m in messages] == ["first", "second"]
        assert all(m.author == "Ada" for m in messages)


class TestArgumentParsingHelpers:
    def test_parse_since_seconds_supports_unit_suffixes(self):
        assert _parse_since_seconds("30m") == 1800
        assert _parse_since_seconds("2h") == 7200
        assert _parse_since_seconds("1d") == 86400

    def test_parse_since_seconds_treats_bare_number_as_hours(self):
        assert _parse_since_seconds("3") == 10800

    @pytest.mark.parametrize("value", [None, "", "abc", "0h", "-5"])
    def test_parse_since_seconds_returns_none_for_invalid(self, value):
        assert _parse_since_seconds(value) is None

    def test_resolve_oldest_uses_default_when_since_absent(self):
        # Absent --since yields None so the caller defaults to channel start.
        assert _resolve_oldest(None) is None

    def test_resolve_oldest_computes_window_from_since(self):
        import time

        before = _resolve_oldest("2h")
        assert before is not None
        assert abs((time.time() - 2 * 3600) - before) < 5

    def test_resolve_limit_defaults_and_caps(self):
        # Fields use env-var aliases, so populate via alias to exercise the
        # logic independently of the production defaults.
        settings = IncidentSummarySettings.model_validate(
            {
                "INCIDENT_SUMMARY__DEFAULT_HISTORY_LIMIT": 200,
                "INCIDENT_SUMMARY__MAX_HISTORY_LIMIT": 500,
            }
        )
        assert _resolve_limit(None, settings) == 200
        assert _resolve_limit(50, settings) == 50
        assert _resolve_limit(9999, settings) == 500
        assert _resolve_limit(0, settings) == 200
        assert _resolve_limit("bad", settings) == 200


class TestResolveDisplayName:
    def test_prefers_display_name(self):
        client = MagicMock()
        client.users_info.return_value = {
            "user": {
                "profile": {"display_name": "Ada", "real_name": "Ada Lovelace"},
                "real_name": "Ada Lovelace",
            }
        }

        name = _resolve_display_name(client, "U1", {}, structlog.get_logger())

        assert name == "Ada"

    def test_falls_back_to_real_name_when_display_name_blank(self):
        client = MagicMock()
        client.users_info.return_value = {
            "user": {
                "profile": {"display_name": "", "real_name": "Ada Lovelace"},
            }
        }

        name = _resolve_display_name(client, "U1", {}, structlog.get_logger())

        assert name == "Ada Lovelace"

    def test_falls_back_to_user_id_on_api_error(self):
        client = MagicMock()
        client.users_info.side_effect = RuntimeError("boom")

        name = _resolve_display_name(client, "U1", {}, structlog.get_logger())

        assert name == "U1"

    def test_caches_lookups_to_avoid_repeat_api_calls(self):
        client = MagicMock()
        client.users_info.return_value = {"user": {"profile": {"display_name": "Ada"}}}
        cache: dict[str, str] = {}
        log = structlog.get_logger()

        first = _resolve_display_name(client, "U1", cache, log)
        second = _resolve_display_name(client, "U1", cache, log)

        assert first == second == "Ada"
        client.users_info.assert_called_once()


class TestToSlackMrkdwn:
    def test_converts_double_asterisk_bold_to_single(self):
        assert _to_slack_mrkdwn("**Key events**") == "*Key events*"

    def test_converts_double_underscore_bold_to_single(self):
        assert _to_slack_mrkdwn("__Key events__") == "*Key events*"

    def test_markdown_heading_becomes_bold_line(self):
        assert _to_slack_mrkdwn("### Key events") == "*Key events*"

    def test_heading_with_bold_markers_is_not_doubled(self):
        assert _to_slack_mrkdwn("## **Key events**") == "*Key events*"

    def test_collapses_double_bullets(self):
        assert _to_slack_mrkdwn("\u2022 \u2022 item") == "\u2022 item"

    def test_dash_bullet_becomes_slack_bullet(self):
        assert _to_slack_mrkdwn("- item") == "\u2022 item"

    def test_mixed_dash_and_bullet_markers_collapse(self):
        assert _to_slack_mrkdwn("- \u2022 item") == "\u2022 item"

    def test_bold_title_line_is_preserved_not_treated_as_bullet(self):
        # A standalone *bold* title must not be mistaken for a bullet marker.
        assert _to_slack_mrkdwn("*Key events*") == "*Key events*"

    def test_plain_text_is_unchanged(self):
        assert _to_slack_mrkdwn("just a sentence") == "just a sentence"

    def test_multiline_document_is_normalized(self):
        raw = "## **Key events**\n- \u2022 first thing\n- second thing"
        expected = "*Key events*\n\u2022 first thing\n\u2022 second thing"
        assert _to_slack_mrkdwn(raw) == expected


class TestResolveChannelStart:
    def test_returns_channel_created_timestamp(self):
        client = MagicMock()
        client.conversations_info.return_value = {"channel": {"created": 1_700_000_000}}
        settings = IncidentSummarySettings(DEFAULT_SINCE_HOURS=24)

        oldest = _resolve_channel_start(client, "C123", settings, structlog.get_logger())

        assert oldest == 1_700_000_000.0

    def test_falls_back_to_default_window_on_api_error(self):
        import time

        client = MagicMock()
        client.conversations_info.side_effect = RuntimeError("no scope")
        settings = IncidentSummarySettings(DEFAULT_SINCE_HOURS=24)

        oldest = _resolve_channel_start(client, "C123", settings, structlog.get_logger())

        assert abs((time.time() - 24 * 3600) - oldest) < 5

    def test_falls_back_when_created_missing(self):
        import time

        client = MagicMock()
        client.conversations_info.return_value = {"channel": {}}
        settings = IncidentSummarySettings(DEFAULT_SINCE_HOURS=24)

        oldest = _resolve_channel_start(client, "C123", settings, structlog.get_logger())

        assert abs((time.time() - 24 * 3600) - oldest) < 5


class TestFetchTranscript:
    def test_returns_empty_list_on_history_api_error(self):
        client = MagicMock()
        client.conversations_history.side_effect = RuntimeError("boom")

        messages = _fetch_transcript(client, "C123", limit=200, oldest=0.0, log=structlog.get_logger())

        assert messages == []

    def test_orders_messages_chronologically(self):
        client = MagicMock()
        client.conversations_history.return_value = {
            "messages": [
                {"user": "U1", "text": "newest", "ts": "3"},
                {"user": "U1", "text": "oldest", "ts": "1"},
            ]
        }
        client.users_info.return_value = {"user": {"profile": {"display_name": "Ada"}}}

        messages = _fetch_transcript(client, "C123", limit=200, oldest=0.0, log=structlog.get_logger())

        assert [m.text for m in messages] == ["oldest", "newest"]
