"""Tests for the incident scribe Slack platform adapter: the summarize command."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contracts.operations import OperationResult
from contracts.slack.models import CommandPayload
from features.incident.scribe.entrypoints.slack import _parse_since_seconds, handle_summarize_command, register
from features.incident.scribe.entrypoints.slack_views import to_slack_mrkdwn
from features.incident.scribe.service import EMPTY_HISTORY_CODE

pytestmark = pytest.mark.unit

_SUMMARIZE = "features.incident.scribe.entrypoints.slack.summarize_incident_conversation"
_HANDLE = "features.incident.scribe.entrypoints.slack.handle_summarize_command"


def _summarize_registration(provider: MagicMock) -> dict:
    """Return the keyword arguments of the ``summarize`` command's registration."""
    (kwargs,) = [call.kwargs for call in provider.register_command.call_args_list if call.kwargs["command"] == "summarize"]
    return kwargs


class TestRegisterCommands:
    def test_registers_summarize_under_sre_incident(self):
        provider = MagicMock()

        register(provider)

        kwargs = _summarize_registration(provider)
        assert kwargs["command"] == "summarize"
        assert kwargs["parent"] == "sre.incident"
        assert kwargs["fallback_handler"] is not None
        assert kwargs["handler"] is not None

    def test_handler_dispatches_with_parsed_args(self):
        provider = MagicMock()
        register(provider)
        handler = _summarize_registration(provider)["handler"]
        payload = CommandPayload(text="--limit 5", user_id="U9", channel_id="C123")

        with patch(_HANDLE) as mock_handle:
            handler(payload, {"--limit": 5})

        mock_handle.assert_called_once_with(payload, {"--limit": 5})

    def test_fallback_dispatches_with_empty_args(self):
        provider = MagicMock()
        register(provider)
        fallback = _summarize_registration(provider)["fallback_handler"]
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_HANDLE) as mock_handle:
            fallback(payload)

        mock_handle.assert_called_once_with(payload, {})


class TestHandleSummarizeCommand:
    def test_success_renders_ephemeral_summary(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="Everything is on fire"))) as mock_service:
            response = handle_summarize_command(payload, {})

        assert response.ephemeral is True
        assert "Everything is on fire" in response.message
        mock_service.assert_awaited_once()
        assert mock_service.await_args.args == ("C123",)

    def test_empty_history_renders_localized_notice(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(
            _SUMMARIZE,
            new=AsyncMock(return_value=OperationResult.permanent_error(message="nothing", error_code=EMPTY_HISTORY_CODE)),
        ):
            response = handle_summarize_command(payload, {})

        assert response.ephemeral is True
        assert "nothing to summarize" in response.message.lower()

    def test_summarizer_error_renders_generic_error(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(
            _SUMMARIZE, new=AsyncMock(return_value=OperationResult.transient_error(message="boom", error_code="SERVER_ERROR"))
        ):
            response = handle_summarize_command(payload, {})

        assert response.ephemeral is True
        assert response.message.startswith("❌")
        assert "nothing to summarize" not in response.message.lower()

    def test_missing_channel_id_returns_error_without_calling_service(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="")

        with patch(_SUMMARIZE, new=AsyncMock()) as mock_service:
            response = handle_summarize_command(payload, {})

        assert response.ephemeral is True
        assert response.message.startswith("\u274c")
        mock_service.assert_not_awaited()

    def test_success_message_includes_header(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="the summary body"))):
            response = handle_summarize_command(payload, {})

        # Header precedes the summary body, separated by a blank line.
        assert response.message.split("\n\n", 1)[0].strip() != ""
        assert not response.message.startswith("the summary body")

    def test_success_message_ends_with_ai_disclaimer_after_the_summary(self):
        """The reader is told, in bold after the summary, that it is AI-generated and needs checking."""
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="the summary body"))):
            response = handle_summarize_command(payload, {})

        assert response.message.endswith(
            "the summary body\n\n*This summary is AI-generated and AI can make mistakes, please review for accuracy.*"
        )

    def test_success_renders_title_as_header_block_then_summary_then_bold_disclaimer(self):
        """Slack shows a header block bold and larger; the plain message stays as the notification fallback."""
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="the summary body"))):
            response = handle_summarize_command(payload, {})

        assert response.blocks is not None
        header, *body, disclaimer = response.blocks
        assert header["type"] == "header"
        assert header["text"]["type"] == "plain_text"
        assert header["text"]["text"].endswith("AI-generated Incident summary")
        assert [block["text"]["text"] for block in body] == ["the summary body"]
        assert disclaimer == {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*This summary is AI-generated and AI can make mistakes, please review for accuracy.*",
            },
        }

    @pytest.mark.parametrize("error_code", [EMPTY_HISTORY_CODE, "SERVER_ERROR"])
    def test_no_disclaimer_when_no_summary_was_generated(self, error_code):
        """Notices and errors carry no AI disclaimer, since no AI text is shown."""
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.permanent_error(message="x", error_code=error_code))):
            response = handle_summarize_command(payload, {})

        assert "AI-generated" not in response.message

    def test_summary_body_is_normalized_to_slack_mrkdwn(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")
        raw = "## **Key events**\n- • first\n- second"

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data=raw))):
            response = handle_summarize_command(payload, {})

        assert "**" not in response.message
        assert "##" not in response.message
        assert "\u2022 \u2022" not in response.message
        assert "*Key events*" in response.message

    def test_limit_argument_is_passed_to_the_service(self):
        payload = CommandPayload(text="--limit 25", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="ok"))) as mock_service:
            handle_summarize_command(payload, {"--limit": 25})

        assert mock_service.await_args.kwargs["limit"] == 25

    @pytest.mark.parametrize("raw", [None, "bad"])
    def test_missing_or_unreadable_limit_is_passed_as_none(self, raw):
        # The service owns the default; the handler only says "no usable limit".
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")
        parsed_args = {} if raw is None else {"--limit": raw}

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="ok"))) as mock_service:
            handle_summarize_command(payload, parsed_args)

        assert mock_service.await_args.kwargs["limit"] is None

    def test_since_argument_is_passed_as_a_duration(self):
        payload = CommandPayload(text="--since 2h", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="ok"))) as mock_service:
            handle_summarize_command(payload, {"--since": "2h"})

        assert mock_service.await_args.kwargs["since"] == timedelta(hours=2)

    @pytest.mark.parametrize("parsed_args", [{}, {"--since": "abc"}, {"--since": "0h"}])
    def test_missing_or_invalid_since_is_passed_as_none(self, parsed_args):
        # No usable look-back: the service starts the window at the conversation's start.
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="ok"))) as mock_service:
            handle_summarize_command(payload, parsed_args)

        assert mock_service.await_args.kwargs["since"] is None

    def test_slack_mrkdwn_instructions_passed_to_service(self):
        payload = CommandPayload(text="", user_id="U9", channel_id="C123")

        with patch(_SUMMARIZE, new=AsyncMock(return_value=OperationResult.success(data="ok"))) as mock_service:
            handle_summarize_command(payload, {})

        instructions = mock_service.await_args.kwargs["instructions"]
        assert "mrkdwn" in instructions.lower()


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


class TestToSlackMrkdwn:
    def test_converts_double_asterisk_bold_to_single(self):
        assert to_slack_mrkdwn("**Key events**") == "*Key events*"

    def test_converts_double_underscore_bold_to_single(self):
        assert to_slack_mrkdwn("__Key events__") == "*Key events*"

    def test_markdown_heading_becomes_bold_line(self):
        assert to_slack_mrkdwn("### Key events") == "*Key events*"

    def test_heading_with_bold_markers_is_not_doubled(self):
        assert to_slack_mrkdwn("## **Key events**") == "*Key events*"

    def test_collapses_double_bullets(self):
        assert to_slack_mrkdwn("\u2022 \u2022 item") == "\u2022 item"

    def test_dash_bullet_becomes_slack_bullet(self):
        assert to_slack_mrkdwn("- item") == "\u2022 item"

    def test_mixed_dash_and_bullet_markers_collapse(self):
        assert to_slack_mrkdwn("- \u2022 item") == "\u2022 item"

    def test_asterisk_bullet_becomes_slack_bullet(self):
        # A Markdown "* item" line is a bullet; the asterisk is followed by whitespace.
        assert to_slack_mrkdwn("* item") == "\u2022 item"

    def test_asterisk_bullet_keeps_bold_text_inside_the_item(self):
        assert to_slack_mrkdwn("* **Next step**: roll back") == "\u2022 *Next step*: roll back"

    def test_bold_title_line_is_preserved_not_treated_as_bullet(self):
        # A standalone *bold* title must not be mistaken for a bullet marker.
        assert to_slack_mrkdwn("*Key events*") == "*Key events*"

    def test_plain_text_is_unchanged(self):
        assert to_slack_mrkdwn("just a sentence") == "just a sentence"

    def test_multiline_document_is_normalized(self):
        raw = "## **Key events**\n- \u2022 first thing\n- second thing"
        expected = "*Key events*\n\u2022 first thing\n\u2022 second thing"
        assert to_slack_mrkdwn(raw) == expected
