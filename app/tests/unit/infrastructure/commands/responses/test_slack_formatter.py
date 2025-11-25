"""Unit tests for Slack response formatter."""

import pytest
from infrastructure.commands.responses.models import (
    Button,
    ButtonStyle,
    Card,
    ErrorMessage,
    Field,
    SuccessMessage,
)
from infrastructure.commands.responses.slack_formatter import SlackResponseFormatter


class TestSlackResponseFormatterText:
    """Tests for SlackResponseFormatter.format_text."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return SlackResponseFormatter()

    def test_format_text_returns_dict_with_text_key(self, formatter):
        """format_text returns dict with text key."""
        result = formatter.format_text("Hello world")

        assert isinstance(result, dict)
        assert "text" in result
        assert result["text"] == "Hello world"

    def test_format_text_handles_empty_string(self, formatter):
        """format_text handles empty string."""
        result = formatter.format_text("")

        assert result["text"] == ""

    def test_format_text_handles_multiline(self, formatter):
        """format_text handles multiline text."""
        text = "Line 1\nLine 2\nLine 3"
        result = formatter.format_text(text)

        assert result["text"] == text

    def test_format_text_handles_special_characters(self, formatter):
        """format_text preserves special characters."""
        text = "Hello! @user #channel :smile:"
        result = formatter.format_text(text)

        assert result["text"] == text


class TestSlackResponseFormatterCard:
    """Tests for SlackResponseFormatter.format_card."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return SlackResponseFormatter()

    def test_format_card_basic(self, formatter):
        """format_card formats basic card."""
        card = Card(title="Test", text="Content")
        result = formatter.format_card(card)

        assert "blocks" in result
        assert "text" in result
        assert isinstance(result["blocks"], list)
        assert result["text"] == "Test"

    def test_format_card_has_header_block(self, formatter):
        """format_card includes header block."""
        card = Card(title="Title", text="Content")
        result = formatter.format_card(card)

        blocks = result["blocks"]
        header = next((b for b in blocks if b["type"] == "header"), None)

        assert header is not None
        assert header["text"]["text"] == "Title"

    def test_format_card_has_text_section(self, formatter):
        """format_card includes text section."""
        card = Card(title="Title", text="Main content")
        result = formatter.format_card(card)

        blocks = result["blocks"]
        sections = [b for b in blocks if b["type"] == "section"]

        assert len(sections) >= 1
        assert "text" in sections[0]
        assert sections[0]["text"]["text"] == "Main content"

    def test_format_card_includes_divider(self, formatter):
        """format_card ends with divider."""
        card = Card(title="Title", text="Content")
        result = formatter.format_card(card)

        blocks = result["blocks"]
        assert blocks[-1]["type"] == "divider"

    def test_format_card_with_fields(self, formatter):
        """format_card includes fields section."""
        fields = [
            Field(title="Status", value="Active"),
            Field(title="Count", value="5"),
        ]
        card = Card(title="Title", text="Content", fields=fields)
        result = formatter.format_card(card)

        blocks = result["blocks"]
        field_block = next((b for b in blocks if b["type"] == "section" and "fields" in b), None)

        assert field_block is not None
        assert len(field_block["fields"]) == 2

    def test_format_card_fields_formatted_correctly(self, formatter):
        """format_card formats fields with title and value."""
        fields = [Field(title="Key", value="Value")]
        card = Card(title="Title", text="Content", fields=fields)
        result = formatter.format_card(card)

        blocks = result["blocks"]
        field_block = next((b for b in blocks if b["type"] == "section" and "fields" in b), None)

        field_text = field_block["fields"][0]["text"]
        assert "*Key*" in field_text
        assert "Value" in field_text

    def test_format_card_without_fields_no_fields_block(self, formatter):
        """format_card without fields has no fields block."""
        card = Card(title="Title", text="Content")
        result = formatter.format_card(card)

        blocks = result["blocks"]
        field_block = next((b for b in blocks if b["type"] == "section" and "fields" in b), None)

        assert field_block is None

    def test_format_card_with_buttons(self, formatter):
        """format_card includes buttons section."""
        buttons = [
            Button(text="Click", action_id="btn_1"),
        ]
        card = Card(title="Title", text="Content", buttons=buttons)
        result = formatter.format_card(card)

        blocks = result["blocks"]
        action_block = next((b for b in blocks if b["type"] == "actions"), None)

        assert action_block is not None
        assert len(action_block["elements"]) == 1

    def test_format_card_button_styles_mapped(self, formatter):
        """format_card maps button styles correctly."""
        buttons = [
            Button(text="Primary", action_id="btn_1", style=ButtonStyle.PRIMARY),
            Button(text="Danger", action_id="btn_2", style=ButtonStyle.DANGER),
            Button(text="Default", action_id="btn_3", style=ButtonStyle.DEFAULT),
        ]
        card = Card(title="Title", text="Content", buttons=buttons)
        result = formatter.format_card(card)

        blocks = result["blocks"]
        action_block = next((b for b in blocks if b["type"] == "actions"), None)

        assert action_block["elements"][0]["style"] == "primary"
        assert action_block["elements"][1]["style"] == "danger"
        assert "style" not in action_block["elements"][2]

    def test_format_card_button_with_value(self, formatter):
        """format_card includes button value."""
        buttons = [Button(text="Action", action_id="btn_1", value="item-123")]
        card = Card(title="Title", text="Content", buttons=buttons)
        result = formatter.format_card(card)

        blocks = result["blocks"]
        action_block = next((b for b in blocks if b["type"] == "actions"), None)

        assert action_block["elements"][0]["value"] == "item-123"

    def test_format_card_without_buttons_no_actions_block(self, formatter):
        """format_card without buttons has no actions block."""
        card = Card(title="Title", text="Content")
        result = formatter.format_card(card)

        blocks = result["blocks"]
        action_block = next((b for b in blocks if b["type"] == "actions"), None)

        assert action_block is None

    def test_format_card_with_image(self, formatter):
        """format_card includes image block."""
        card = Card(
            title="Title",
            text="Content",
            image_url="https://example.com/image.png",
        )
        result = formatter.format_card(card)

        blocks = result["blocks"]
        image_block = next((b for b in blocks if b["type"] == "image"), None)

        assert image_block is not None
        assert image_block["image_url"] == "https://example.com/image.png"
        assert image_block["alt_text"] == "Title"

    def test_format_card_without_image_no_image_block(self, formatter):
        """format_card without image has no image block."""
        card = Card(title="Title", text="Content")
        result = formatter.format_card(card)

        blocks = result["blocks"]
        image_block = next((b for b in blocks if b["type"] == "image"), None)

        assert image_block is None

    def test_format_card_with_footer(self, formatter):
        """format_card includes footer context."""
        card = Card(title="Title", text="Content", footer="Generated by bot")
        result = formatter.format_card(card)

        blocks = result["blocks"]
        context_block = next((b for b in blocks if b["type"] == "context"), None)

        assert context_block is not None
        assert "Generated by bot" in context_block["elements"][0]["text"]

    def test_format_card_without_footer_no_context_block(self, formatter):
        """format_card without footer has no context block."""
        card = Card(title="Title", text="Content")
        result = formatter.format_card(card)

        blocks = result["blocks"]
        context_block = next((b for b in blocks if b["type"] == "context"), None)

        assert context_block is None

    def test_format_card_with_color(self, formatter):
        """format_card preserves color (not in Slack format)."""
        card = Card(title="Title", text="Content", color="#FF0000")
        result = formatter.format_card(card)

        # Color is not directly in Slack blocks but stored in card
        assert isinstance(result["blocks"], list)

    def test_format_card_complex_with_all_elements(self, formatter):
        """format_card with all elements."""
        card = Card(
            title="Complex",
            text="Main content",
            color="#36a64f",
            fields=[Field(title="Status", value="Active")],
            buttons=[Button(text="Action", action_id="btn_1")],
            footer="Footer text",
            image_url="https://example.com/img.png",
        )
        result = formatter.format_card(card)

        blocks = result["blocks"]
        assert any(b["type"] == "header" for b in blocks)
        assert any(b["type"] == "section" for b in blocks)
        assert any(b["type"] == "image" for b in blocks)
        assert any(b["type"] == "actions" for b in blocks)
        assert any(b["type"] == "context" for b in blocks)
        assert any(b["type"] == "divider" for b in blocks)


class TestSlackResponseFormatterError:
    """Tests for SlackResponseFormatter.format_error."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return SlackResponseFormatter()

    def test_format_error_basic(self, formatter):
        """format_error formats basic error."""
        error = ErrorMessage(message="Something failed")
        result = formatter.format_error(error)

        assert "blocks" in result
        assert "text" in result
        assert ":x:" in result["text"]

    def test_format_error_includes_message(self, formatter):
        """format_error includes error message."""
        error = ErrorMessage(message="Operation failed")
        result = formatter.format_error(error)

        blocks = result["blocks"]
        section = blocks[0]

        assert "Operation failed" in section["text"]["text"]

    def test_format_error_with_details(self, formatter):
        """format_error includes details section."""
        error = ErrorMessage(
            message="Failed",
            details="Detailed error information",
        )
        result = formatter.format_error(error)

        blocks = result["blocks"]
        details_block = next((b for b in blocks if "Detailed error information" in str(b)), None)

        assert details_block is not None

    def test_format_error_details_in_code_block(self, formatter):
        """format_error formats details in code block."""
        error = ErrorMessage(message="Failed", details="Traceback data")
        result = formatter.format_error(error)

        blocks = result["blocks"]
        # Look for code formatting
        found_code = any("```" in str(b) for b in blocks)
        assert found_code

    def test_format_error_without_details(self, formatter):
        """format_error without details works."""
        error = ErrorMessage(message="Error")
        result = formatter.format_error(error)

        blocks = result["blocks"]
        assert len(blocks) >= 1

    def test_format_error_with_error_code(self, formatter):
        """format_error includes error code."""
        error = ErrorMessage(
            message="Failed",
            error_code="ERR_OPERATION_FAILED",
        )
        result = formatter.format_error(error)

        blocks = result["blocks"]
        code_block = next((b for b in blocks if "ERR_OPERATION_FAILED" in str(b)), None)

        assert code_block is not None

    def test_format_error_error_code_in_backticks(self, formatter):
        """format_error formats error code in backticks."""
        error = ErrorMessage(message="Failed", error_code="ERR_001")
        result = formatter.format_error(error)

        blocks = result["blocks"]
        found_code = any("`ERR_001`" in str(b) for b in blocks)
        assert found_code

    def test_format_error_without_error_code(self, formatter):
        """format_error without error code works."""
        error = ErrorMessage(message="Error", details="Details")
        result = formatter.format_error(error)

        blocks = result["blocks"]
        assert len(blocks) >= 2

    def test_format_error_fallback_text(self, formatter):
        """format_error includes fallback text."""
        error = ErrorMessage(message="Operation failed")
        result = formatter.format_error(error)

        assert "text" in result
        assert ":x:" in result["text"]
        assert "Operation failed" in result["text"]


class TestSlackResponseFormatterSuccess:
    """Tests for SlackResponseFormatter.format_success."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return SlackResponseFormatter()

    def test_format_success_basic(self, formatter):
        """format_success formats basic success."""
        success = SuccessMessage(message="Operation completed")
        result = formatter.format_success(success)

        assert "blocks" in result
        assert "text" in result
        assert ":white_check_mark:" in result["text"]

    def test_format_success_includes_message(self, formatter):
        """format_success includes success message."""
        success = SuccessMessage(message="Successfully processed")
        result = formatter.format_success(success)

        blocks = result["blocks"]
        section = blocks[0]

        assert "Successfully processed" in section["text"]["text"]

    def test_format_success_with_details(self, formatter):
        """format_success includes details context."""
        success = SuccessMessage(
            message="Success",
            details="5 items processed",
        )
        result = formatter.format_success(success)

        blocks = result["blocks"]
        context = next((b for b in blocks if b["type"] == "context"), None)

        assert context is not None
        assert "5 items processed" in context["elements"][0]["text"]

    def test_format_success_without_details(self, formatter):
        """format_success without details works."""
        success = SuccessMessage(message="Done")
        result = formatter.format_success(success)

        blocks = result["blocks"]
        assert len(blocks) >= 1

    def test_format_success_fallback_text(self, formatter):
        """format_success includes fallback text."""
        success = SuccessMessage(message="Completed")
        result = formatter.format_success(success)

        assert "text" in result
        assert ":white_check_mark:" in result["text"]
        assert "Completed" in result["text"]


class TestSlackResponseFormatterButtonStyleMapping:
    """Tests for button style mapping."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return SlackResponseFormatter()

    def test_map_button_style_primary(self, formatter):
        """_map_button_style maps PRIMARY to 'primary'."""
        result = formatter._map_button_style(ButtonStyle.PRIMARY)
        assert result == "primary"

    def test_map_button_style_danger(self, formatter):
        """_map_button_style maps DANGER to 'danger'."""
        result = formatter._map_button_style(ButtonStyle.DANGER)
        assert result == "danger"

    def test_map_button_style_default_to_empty(self, formatter):
        """_map_button_style maps DEFAULT to empty string."""
        result = formatter._map_button_style(ButtonStyle.DEFAULT)
        assert result == ""
