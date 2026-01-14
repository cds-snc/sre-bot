"""Unit tests for Microsoft Teams Adaptive Cards formatter.

Tests verify Adaptive Card schema compliance, proper formatting, and styling.
"""

import pytest

from infrastructure.platforms.formatters.teams import TeamsAdaptiveCardsFormatter


@pytest.mark.unit
class TestTeamsAdaptiveCardsFormatterInitialization:
    """Test formatter initialization."""

    def test_initialization(self):
        """Test formatter initializes successfully."""
        formatter = TeamsAdaptiveCardsFormatter()

        assert formatter.SCHEMA_VERSION == "1.4"
        assert formatter._locale == "en"

    def test_initialization_sets_schema_version(self):
        """Test formatter uses Adaptive Cards schema version 1.4."""
        formatter = TeamsAdaptiveCardsFormatter()

        # Build a card to verify schema version is used
        card = formatter.format_info("Test message")
        content = card["attachments"][0]["content"]

        assert content["version"] == "1.4"
        assert (
            content["$schema"] == "http://adaptivecards.io/schemas/adaptive-card.json"
        )


@pytest.mark.unit
class TestFormatSuccess:
    """Test format_success method."""

    def test_format_success_basic(self):
        """Test formatting successful result with message only."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_success(
            data={}, message="Operation completed successfully"
        )

        # Verify message structure
        assert card["type"] == "message"
        assert len(card["attachments"]) == 1

        # Verify Adaptive Card content
        content = card["attachments"][0]["content"]
        assert content["type"] == "AdaptiveCard"
        assert content["version"] == "1.4"

        # Verify body has title and message
        body = content["body"]
        assert len(body) == 2
        assert body[0]["type"] == "TextBlock"
        assert body[0]["text"] == "✅ Success"
        assert body[0]["color"] == "Good"
        assert body[1]["text"] == "Operation completed successfully"

    def test_format_success_with_data(self):
        """Test formatting successful result with data fields."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_success(
            data={"user_id": "U123", "email": "test@example.com", "role": "admin"},
            message="User created",
        )
        body = card["attachments"][0]["content"]["body"]

        # Should have title, message, and FactSet
        assert len(body) == 3
        assert body[2]["type"] == "FactSet"

        # Verify facts
        facts = body[2]["facts"]
        assert len(facts) == 3
        assert {"title": "user_id", "value": "U123"} in facts
        assert {"title": "email", "value": "test@example.com"} in facts
        assert {"title": "role", "value": "admin"} in facts

    def test_format_success_has_green_accent(self):
        """Test successful result has green accent color."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_success(data={}, message="Success message")
        content = card["attachments"][0]["content"]

        assert content["accentColor"] == "#28A745"  # Green

    def test_format_success_without_data(self):
        """Test formatting success without data doesn't include FactSet."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_success(data={}, message="Done")
        body = card["attachments"][0]["content"]["body"]

        # Should only have title and message
        assert len(body) == 2
        assert all(block["type"] == "TextBlock" for block in body)

    def test_format_success_with_empty_data(self):
        """Test formatting success with empty data dict."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_success(data={}, message="Done")
        body = card["attachments"][0]["content"]["body"]

        # Should only have title and message (no FactSet for empty dict)
        assert len(body) == 2


@pytest.mark.unit
class TestFormatError:
    """Test format_error method."""

    def test_format_error_basic(self):
        """Test formatting error result with message only."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_error(message="Operation failed")

        # Verify message structure
        assert card["type"] == "message"
        assert len(card["attachments"]) == 1

        # Verify Adaptive Card content
        content = card["attachments"][0]["content"]
        assert content["type"] == "AdaptiveCard"

        # Verify body has title and message
        body = content["body"]
        assert len(body) == 2
        assert body[0]["text"] == "❌ Error"
        assert body[0]["color"] == "Attention"
        assert body[1]["text"] == "Operation failed"

    def test_format_error_with_error_code(self):
        """Test formatting error result with error code."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_error(
            message="Validation failed", error_code="INVALID_INPUT"
        )
        body = card["attachments"][0]["content"]["body"]

        # Should have title, message, and error code
        assert len(body) == 3
        assert body[2]["type"] == "TextBlock"
        assert body[2]["text"] == "Error Code: INVALID_INPUT"
        assert body[2]["isSubtle"] is True

    def test_format_error_has_red_accent(self):
        """Test error result has red accent color."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_error(message="Error message")
        content = card["attachments"][0]["content"]

        assert content["accentColor"] == "#DC3545"  # Red

    def test_format_error_without_error_code(self):
        """Test formatting error without error code."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_error(message="Generic error")
        body = card["attachments"][0]["content"]["body"]

        # Should only have title and message
        assert len(body) == 2

    def test_format_error_transient(self):
        """Test formatting transient error."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_error(message="Network timeout", error_code="TIMEOUT")
        body = card["attachments"][0]["content"]["body"]

        assert body[0]["text"] == "❌ Error"
        assert body[1]["text"] == "Network timeout"
        assert body[2]["text"] == "Error Code: TIMEOUT"


@pytest.mark.unit
class TestFormatInfo:
    """Test format_info method."""

    def test_format_info_basic(self):
        """Test formatting informational message."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_info(message="Processing your request...")

        # Verify structure
        content = card["attachments"][0]["content"]
        body = content["body"]

        assert len(body) == 2
        assert body[0]["text"] == "ℹ️ Info"
        assert body[0]["color"] == "Default"
        assert body[1]["text"] == "Processing your request..."

    def test_format_info_with_data(self):
        """Test formatting info message with data."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_info(
            message="Request queued",
            data={"position": "3", "estimated_time": "2 minutes"},
        )

        body = card["attachments"][0]["content"]["body"]

        # Should have title, message, and FactSet
        assert len(body) == 3
        assert body[2]["type"] == "FactSet"

        facts = body[2]["facts"]
        assert len(facts) == 2
        assert {"title": "position", "value": "3"} in facts
        assert {"title": "estimated_time", "value": "2 minutes"} in facts

    def test_format_info_has_blue_accent(self):
        """Test info message has blue accent color."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_info(message="Info message")
        content = card["attachments"][0]["content"]

        assert content["accentColor"] == "#17A2B8"  # Blue

    def test_format_info_without_data(self):
        """Test formatting info without data."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_info(message="Simple info")
        body = card["attachments"][0]["content"]["body"]

        # Should only have title and message
        assert len(body) == 2


@pytest.mark.unit
class TestFormatWarning:
    """Test format_warning method."""

    def test_format_warning_basic(self):
        """Test formatting warning message."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_warning(message="Quota limit approaching")

        # Verify structure
        content = card["attachments"][0]["content"]
        body = content["body"]

        assert len(body) == 2
        assert body[0]["text"] == "⚠️ Warning"
        assert body[0]["color"] == "Warning"
        assert body[1]["text"] == "Quota limit approaching"

    def test_format_warning_with_data(self):
        """Test formatting warning with data."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_warning(
            message="High memory usage",
            data={"memory_used": "85%", "threshold": "80%"},
        )

        body = card["attachments"][0]["content"]["body"]

        # Should have title, message, and FactSet
        assert len(body) == 3
        facts = body[2]["facts"]
        assert len(facts) == 2
        assert {"title": "memory_used", "value": "85%"} in facts
        assert {"title": "threshold", "value": "80%"} in facts

    def test_format_warning_has_yellow_accent(self):
        """Test warning message has yellow accent color."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_warning(message="Warning message")
        content = card["attachments"][0]["content"]

        assert content["accentColor"] == "#FFC107"  # Yellow

    def test_format_warning_without_data(self):
        """Test formatting warning without data."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_warning(message="Simple warning")
        body = card["attachments"][0]["content"]["body"]

        # Should only have title and message
        assert len(body) == 2


@pytest.mark.unit
class TestBuildAdaptiveCard:
    """Test _build_adaptive_card helper method."""

    def test_build_adaptive_card_structure(self):
        """Test basic Adaptive Card structure."""
        formatter = TeamsAdaptiveCardsFormatter()

        body = [{"type": "TextBlock", "text": "Test"}]
        card = formatter._build_adaptive_card(body=body)

        assert card["type"] == "message"
        assert len(card["attachments"]) == 1

        attachment = card["attachments"][0]
        assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"

        content = attachment["content"]
        assert (
            content["$schema"] == "http://adaptivecards.io/schemas/adaptive-card.json"
        )
        assert content["type"] == "AdaptiveCard"
        assert content["version"] == "1.4"
        assert content["body"] == body

    def test_build_adaptive_card_with_accent_color(self):
        """Test Adaptive Card with accent color."""
        formatter = TeamsAdaptiveCardsFormatter()

        body = [{"type": "TextBlock", "text": "Test"}]
        card = formatter._build_adaptive_card(body=body, accent_color="#FF5733")

        content = card["attachments"][0]["content"]
        assert content["accentColor"] == "#FF5733"

    def test_build_adaptive_card_without_accent_color(self):
        """Test Adaptive Card without accent color."""
        formatter = TeamsAdaptiveCardsFormatter()

        body = [{"type": "TextBlock", "text": "Test"}]
        card = formatter._build_adaptive_card(body=body)

        content = card["attachments"][0]["content"]
        assert "accentColor" not in content


@pytest.mark.unit
class TestAdaptiveCardCompliance:
    """Test Adaptive Card schema compliance."""

    def test_card_has_required_fields(self):
        """Test all cards have required Adaptive Card fields."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_success(data={}, message="Test")
        content = card["attachments"][0]["content"]

        # Required fields per Adaptive Cards schema
        assert "$schema" in content
        assert content["type"] == "AdaptiveCard"
        assert "version" in content
        assert "body" in content

    def test_text_blocks_are_wrapped(self):
        """Test TextBlocks have wrap=True for long text."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_info(message="This is a long message that should wrap")
        body = card["attachments"][0]["content"]["body"]

        # Message TextBlock should have wrap=True
        message_block = body[1]
        assert message_block["wrap"] is True

    def test_facts_have_required_structure(self):
        """Test FactSet facts have title and value."""
        formatter = TeamsAdaptiveCardsFormatter()

        card = formatter.format_success(data={"key": "value"}, message="Test")
        fact_set = card["attachments"][0]["content"]["body"][2]

        assert fact_set["type"] == "FactSet"
        for fact in fact_set["facts"]:
            assert "title" in fact
            assert "value" in fact
            assert isinstance(fact["title"], str)
            assert isinstance(fact["value"], str)
