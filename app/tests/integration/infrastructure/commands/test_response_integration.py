"""Integration tests for response handling in command framework."""

import pytest
from unittest.mock import MagicMock

from infrastructure.commands.responses.models import (
    Button,
    ButtonStyle,
    Card,
    ErrorMessage,
    Field,
    SuccessMessage,
)
from infrastructure.commands.providers.slack import SlackResponseChannel


class TestSlackResponseChannelIntegration:
    """Integration tests for SlackResponseChannel with formatter."""

    @pytest.fixture
    def mock_respond(self):
        """Mock Slack respond function."""
        return MagicMock()

    @pytest.fixture
    def mock_client(self):
        """Mock Slack client."""
        return MagicMock()

    @pytest.fixture
    def response_channel(self, mock_respond, mock_client):
        """Create SlackResponseChannel instance."""
        return SlackResponseChannel(
            respond=mock_respond,
            client=mock_client,
            channel_id="C123",
            user_id="U123",
        )

    def test_send_card_calls_respond_with_formatted_blocks(
        self, response_channel, mock_respond
    ):
        """send_card calls respond with formatted blocks."""
        card = Card(title="Test", text="Content")

        response_channel.send_card(card)

        mock_respond.assert_called_once()
        call_kwargs = mock_respond.call_args[1]
        assert "blocks" in call_kwargs
        assert isinstance(call_kwargs["blocks"], list)

    def test_send_card_with_fields_includes_fields_in_blocks(
        self, response_channel, mock_respond
    ):
        """send_card with fields includes fields in blocks."""
        card = Card(
            title="Test",
            text="Content",
            fields=[Field(title="Status", value="Active")],
        )

        response_channel.send_card(card)

        call_kwargs = mock_respond.call_args[1]
        blocks = call_kwargs["blocks"]

        # Verify fields are in blocks
        field_blocks = [b for b in blocks if "fields" in b]
        assert len(field_blocks) > 0

    def test_send_card_with_buttons_includes_buttons_in_blocks(
        self, response_channel, mock_respond
    ):
        """send_card with buttons includes buttons in blocks."""
        card = Card(
            title="Test",
            text="Content",
            buttons=[Button(text="Click", action_id="btn_1")],
        )

        response_channel.send_card(card)

        call_kwargs = mock_respond.call_args[1]
        blocks = call_kwargs["blocks"]

        # Verify actions are in blocks
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) > 0

    def test_send_card_passes_additional_kwargs(self, response_channel, mock_respond):
        """send_card passes additional kwargs to respond."""
        card = Card(title="Test", text="Content")

        response_channel.send_card(card, thread_ts="1234567890")

        call_kwargs = mock_respond.call_args[1]
        assert call_kwargs["thread_ts"] == "1234567890"

    def test_send_error_calls_respond_with_formatted_blocks(
        self, response_channel, mock_respond
    ):
        """send_error calls respond with formatted error blocks."""
        error = ErrorMessage(message="Something failed")

        response_channel.send_error(error)

        mock_respond.assert_called_once()
        call_kwargs = mock_respond.call_args[1]
        assert "blocks" in call_kwargs
        assert "text" in call_kwargs
        assert ":x:" in call_kwargs["text"]

    def test_send_error_with_details_includes_details(
        self, response_channel, mock_respond
    ):
        """send_error with details includes details in blocks."""
        error = ErrorMessage(
            message="Failed",
            details="Traceback information",
            error_code="ERR_001",
        )

        response_channel.send_error(error)

        call_kwargs = mock_respond.call_args[1]
        blocks = call_kwargs["blocks"]

        # Verify error details are formatted
        blocks_str = str(blocks)
        assert "Traceback information" in blocks_str
        assert "ERR_001" in blocks_str

    def test_send_error_passes_additional_kwargs(self, response_channel, mock_respond):
        """send_error passes additional kwargs to respond."""
        error = ErrorMessage(message="Error")

        response_channel.send_error(error, thread_ts="1234567890")

        call_kwargs = mock_respond.call_args[1]
        assert call_kwargs["thread_ts"] == "1234567890"

    def test_send_success_calls_respond_with_formatted_blocks(
        self, response_channel, mock_respond
    ):
        """send_success calls respond with formatted success blocks."""
        success = SuccessMessage(message="Operation completed")

        response_channel.send_success(success)

        mock_respond.assert_called_once()
        call_kwargs = mock_respond.call_args[1]
        assert "blocks" in call_kwargs
        assert "text" in call_kwargs
        assert ":white_check_mark:" in call_kwargs["text"]

    def test_send_success_with_details_includes_details(
        self, response_channel, mock_respond
    ):
        """send_success with details includes details in blocks."""
        success = SuccessMessage(
            message="Success",
            details="5 items processed successfully",
        )

        response_channel.send_success(success)

        call_kwargs = mock_respond.call_args[1]
        blocks = call_kwargs["blocks"]

        # Verify success details are formatted
        blocks_str = str(blocks)
        assert "5 items processed successfully" in blocks_str

    def test_send_success_passes_additional_kwargs(
        self, response_channel, mock_respond
    ):
        """send_success passes additional kwargs to respond."""
        success = SuccessMessage(message="Done")

        response_channel.send_success(success, thread_ts="1234567890")

        call_kwargs = mock_respond.call_args[1]
        assert call_kwargs["thread_ts"] == "1234567890"

    def test_complex_card_end_to_end(self, response_channel, mock_respond):
        """End-to-end test with complex card containing all elements."""
        card = Card(
            title="Report",
            text="Processing Results",
            color="#36a64f",
            fields=[
                Field(title="Total", value="100"),
                Field(title="Processed", value="95", short=True),
                Field(title="Failed", value="5", short=True),
            ],
            buttons=[
                Button(text="Confirm", action_id="confirm", style=ButtonStyle.PRIMARY),
                Button(text="Cancel", action_id="cancel"),
            ],
            footer="Generated by SRE Bot",
            image_url="https://example.com/chart.png",
        )

        response_channel.send_card(card)

        # Verify respond was called
        mock_respond.assert_called_once()

        call_kwargs = mock_respond.call_args[1]
        blocks = call_kwargs["blocks"]

        # Verify all block types are present
        block_types = {b["type"] for b in blocks}
        assert "header" in block_types
        assert "section" in block_types
        assert "actions" in block_types
        assert "image" in block_types
        assert "context" in block_types
        assert "divider" in block_types

    def test_message_and_card_both_work(self, response_channel, mock_respond):
        """Both send_message and send_card work together."""
        # Send regular message
        response_channel.send_message("Starting operation...")

        # Send card
        card = Card(title="Status", text="Operation in progress")
        response_channel.send_card(card)

        # Both should have been called
        assert mock_respond.call_count == 2

        # First call is message
        assert mock_respond.call_args_list[0][1]["text"] == "Starting operation..."

        # Second call is card with blocks
        assert "blocks" in mock_respond.call_args_list[1][1]

    def test_error_and_success_messages_both_work(self, response_channel, mock_respond):
        """Both send_error and send_success work together."""
        # Send error first
        error = ErrorMessage(message="Operation failed")
        response_channel.send_error(error)

        # Send success
        success = SuccessMessage(message="Recovery successful")
        response_channel.send_success(success)

        # Both should have been called
        assert mock_respond.call_count == 2

        # Verify error formatting
        error_call = mock_respond.call_args_list[0][1]
        assert ":x:" in error_call["text"]

        # Verify success formatting
        success_call = mock_respond.call_args_list[1][1]
        assert ":white_check_mark:" in success_call["text"]

    def test_formatter_reused_across_calls(self, response_channel, mock_respond):
        """Formatter is reused across multiple calls."""
        # Get initial formatter
        initial_formatter = response_channel.formatter

        # Call send_card multiple times
        card1 = Card(title="Card 1", text="Content 1")
        card2 = Card(title="Card 2", text="Content 2")

        response_channel.send_card(card1)
        response_channel.send_card(card2)

        # Formatter should be the same instance
        assert response_channel.formatter is initial_formatter

        # Both calls should have succeeded
        assert mock_respond.call_count == 2
