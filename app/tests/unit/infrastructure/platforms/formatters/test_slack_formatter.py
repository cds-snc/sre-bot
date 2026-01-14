"""Unit tests for SlackBlockKitFormatter."""

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.platforms.formatters.slack import SlackBlockKitFormatter


class MockTranslator:
    """Mock translator for testing."""

    def translate(self, key: str, locale: str = "en-US", **kwargs) -> str:
        """Mock translate method."""
        return f"[{locale.upper()}] {key}"


@pytest.mark.unit
class TestSlackBlockKitFormatter:
    """Test SlackBlockKitFormatter initialization and basic operations."""

    def test_initialization(self):
        """Test formatter initialization."""
        formatter = SlackBlockKitFormatter()

        assert formatter.locale == "en-US"
        assert formatter._translation_service is None

    def test_initialization_with_locale(self):
        """Test formatter with custom locale."""
        formatter = SlackBlockKitFormatter(locale="fr")

        assert formatter.locale == "fr"

    def test_initialization_with_translation_service(self):
        """Test formatter with translator."""
        translator = MockTranslator()
        formatter = SlackBlockKitFormatter(translation_service=translator)

        assert formatter._translation_service is translator


@pytest.mark.unit
class TestFormatSuccess:
    """Test format_success() method."""

    def test_format_success_minimal(self):
        """Test success formatting with minimal data."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_success(data={})

        assert "blocks" in result
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["type"] == "section"
        assert ":white_check_mark:" in result["blocks"][0]["text"]["text"]
        assert "Success" in result["blocks"][0]["text"]["text"]

    def test_format_success_with_message(self):
        """Test success formatting with custom message."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_success(data={}, message="Operation completed")

        assert "blocks" in result
        header_text = result["blocks"][0]["text"]["text"]
        assert "Operation completed" in header_text
        assert ":white_check_mark:" in header_text

    def test_format_success_with_data(self):
        """Test success formatting with data payload."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_success(
            data={"user_id": "U123", "status": "active"},
            message="User created",
        )

        assert "blocks" in result
        assert len(result["blocks"]) >= 3  # header + divider + data
        # Should have divider
        assert any(block["type"] == "divider" for block in result["blocks"])
        # Should format data
        data_text = result["blocks"][-1]["text"]["text"]
        assert "User Id" in data_text
        assert "U123" in data_text

    def test_format_success_with_boolean_data(self):
        """Test success formatting with boolean values."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_success(data={"enabled": True, "verified": False})

        data_text = result["blocks"][-1]["text"]["text"]
        assert ":white_check_mark:" in data_text  # For True
        assert ":x:" in data_text  # For False


@pytest.mark.unit
class TestFormatError:
    """Test format_error() method."""

    def test_format_error_minimal(self):
        """Test error formatting with only message."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_error(message="Something went wrong")

        assert "blocks" in result
        assert len(result["blocks"]) == 1
        header_text = result["blocks"][0]["text"]["text"]
        assert ":x:" in header_text
        assert "Something went wrong" in header_text

    def test_format_error_with_code(self):
        """Test error formatting with error code."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_error(message="User not found", error_code="USER_404")

        assert "blocks" in result
        assert len(result["blocks"]) >= 2
        # Should have context block with error code
        context_blocks = [b for b in result["blocks"] if b["type"] == "context"]
        assert len(context_blocks) == 1
        assert "USER_404" in context_blocks[0]["elements"][0]["text"]

    def test_format_error_with_details(self):
        """Test error formatting with details."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_error(
            message="Validation failed",
            error_code="VALIDATION_ERROR",
            details={"field": "email", "reason": "invalid"},
        )

        assert "blocks" in result
        # Should have divider and details section
        assert any(block["type"] == "divider" for block in result["blocks"])
        data_text = result["blocks"][-1]["text"]["text"]
        assert "Field" in data_text
        assert "email" in data_text

    def test_format_error_minimal_no_extras(self):
        """Test error formatting without code or details."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_error(
            message="Error occurred", error_code=None, details=None
        )

        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["type"] == "section"


@pytest.mark.unit
class TestFormatInfo:
    """Test format_info() method."""

    def test_format_info_minimal(self):
        """Test info formatting with only message."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_info(message="Processing...")

        assert "blocks" in result
        assert len(result["blocks"]) == 1
        header_text = result["blocks"][0]["text"]["text"]
        assert ":information_source:" in header_text
        assert "Processing..." in header_text

    def test_format_info_with_data(self):
        """Test info formatting with data."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_info(
            message="Status update", data={"progress": 50, "total": 100}
        )

        assert "blocks" in result
        assert len(result["blocks"]) >= 3  # header + divider + data
        assert any(block["type"] == "divider" for block in result["blocks"])

    def test_format_info_without_data(self):
        """Test info formatting explicitly without data."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_info(message="System ready", data=None)

        assert len(result["blocks"]) == 1


@pytest.mark.unit
class TestFormatWarning:
    """Test format_warning() method."""

    def test_format_warning_minimal(self):
        """Test warning formatting with only message."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_warning(message="Low disk space")

        assert "blocks" in result
        assert len(result["blocks"]) == 1
        header_text = result["blocks"][0]["text"]["text"]
        assert ":warning:" in header_text
        assert "Low disk space" in header_text

    def test_format_warning_with_data(self):
        """Test warning formatting with data."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_warning(
            message="Resource limit approaching",
            data={"current": 90, "limit": 100},
        )

        assert "blocks" in result
        assert len(result["blocks"]) >= 3
        data_text = result["blocks"][-1]["text"]["text"]
        assert "Current" in data_text
        assert "90" in data_text


@pytest.mark.unit
class TestFormatOperationResult:
    """Test format_operation_result() integration."""

    def test_format_successful_operation_result(self):
        """Test formatting successful OperationResult."""
        formatter = SlackBlockKitFormatter()
        result = OperationResult.success(
            data={"user_id": "U123"}, message="User created"
        )

        formatted = formatter.format_operation_result(result)

        assert "blocks" in formatted
        header_text = formatted["blocks"][0]["text"]["text"]
        assert ":white_check_mark:" in header_text
        assert "User created" in header_text

    def test_format_error_operation_result(self):
        """Test formatting error OperationResult."""
        formatter = SlackBlockKitFormatter()
        result = OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message="User not found",
            error_code="USER_404",
        )

        formatted = formatter.format_operation_result(result)

        assert "blocks" in formatted
        header_text = formatted["blocks"][0]["text"]["text"]
        assert ":x:" in header_text
        assert "User not found" in header_text

    def test_format_operation_result_without_message(self):
        """Test formatting OperationResult with no message."""
        formatter = SlackBlockKitFormatter()
        result = OperationResult(
            status=OperationStatus.SUCCESS, message=None, data={"id": "123"}
        )

        formatted = formatter.format_operation_result(result)

        assert "blocks" in formatted
        # Should use default "ok" message from OperationResult.success()
        # or handle None gracefully


@pytest.mark.unit
class TestBlockCreationHelpers:
    """Test internal block creation helper methods."""

    def test_create_section(self):
        """Test _create_section() helper."""
        formatter = SlackBlockKitFormatter()

        block = formatter._create_section("Test message")

        assert block["type"] == "section"
        assert block["text"]["type"] == "mrkdwn"
        assert block["text"]["text"] == "Test message"

    def test_create_context(self):
        """Test _create_context() helper."""
        formatter = SlackBlockKitFormatter()

        block = formatter._create_context(["Line 1", "Line 2"])

        assert block["type"] == "context"
        assert len(block["elements"]) == 2
        assert block["elements"][0]["type"] == "mrkdwn"
        assert block["elements"][0]["text"] == "Line 1"
        assert block["elements"][1]["text"] == "Line 2"

    def test_format_data_as_text_simple(self):
        """Test _format_data_as_text() with simple data."""
        formatter = SlackBlockKitFormatter()

        text = formatter._format_data_as_text({"user_id": "U123", "count": 42})

        assert "User Id" in text
        assert "U123" in text
        assert "Count" in text
        assert "42" in text

    def test_format_data_as_text_empty(self):
        """Test _format_data_as_text() with empty dict."""
        formatter = SlackBlockKitFormatter()

        text = formatter._format_data_as_text({})

        assert text == ""

    def test_format_data_as_text_with_list(self):
        """Test _format_data_as_text() with list value."""
        formatter = SlackBlockKitFormatter()

        text = formatter._format_data_as_text({"items": [1, 2, 3]})

        assert "Items" in text
        assert "list" in text

    def test_format_data_as_text_with_dict(self):
        """Test _format_data_as_text() with nested dict value."""
        formatter = SlackBlockKitFormatter()

        text = formatter._format_data_as_text({"config": {"key": "value"}})

        assert "Config" in text
        assert "dict" in text


@pytest.mark.unit
class TestBlockKitStructure:
    """Test Block Kit JSON structure compliance."""

    def test_success_blocks_structure(self):
        """Test that success response has valid Block Kit structure."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_success(data={"id": "123"}, message="Created")

        # Should have blocks array
        assert "blocks" in result
        assert isinstance(result["blocks"], list)
        # Each block should have a type
        for block in result["blocks"]:
            assert "type" in block
            assert block["type"] in [
                "section",
                "divider",
                "context",
                "actions",
            ]

    def test_error_blocks_structure(self):
        """Test that error response has valid Block Kit structure."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_error(
            message="Error", error_code="ERR", details={"x": "y"}
        )

        assert "blocks" in result
        assert isinstance(result["blocks"], list)
        for block in result["blocks"]:
            assert "type" in block

    def test_section_block_has_text(self):
        """Test that section blocks have required text field."""
        formatter = SlackBlockKitFormatter()

        result = formatter.format_info(message="Info")

        section_blocks = [b for b in result["blocks"] if b["type"] == "section"]
        for block in section_blocks:
            assert "text" in block
            assert "type" in block["text"]
            assert "text" in block["text"]
