from models.webhooks import WebhookPayload
from modules.webhooks.patterns.simple_text.upptime import (
    handle_upptime_payload,
    is_upptime_pattern,
    UPPTIME_HANDLER,
    register_upptime_pattern,
)
from modules.webhooks.simple_text import PATTERN_HANDLERS, SimpleTextPattern


def test_handle_upptime_payload_service_down():
    """Test handling of service down alerts."""
    text = "🟥 Payload Test (https://not-valid.cdssandbox.xyz/) is **down** : https://github.com/cds-snc/status-statut/issues/222"
    result = handle_upptime_payload(text)

    assert isinstance(result, WebhookPayload)
    assert len(result.blocks) == 3
    assert result.blocks[0]["type"] == "section"
    assert result.blocks[1]["type"] == "header"
    assert result.blocks[1]["text"]["text"] == "🚨 Service Down Alert"
    assert result.blocks[2]["type"] == "section"
    assert result.blocks[2]["text"]["text"] == text


def test_handle_upptime_payload_service_down_large_red_square():
    """Test handling of service down with :large_red_square: indicator."""
    text = ":large_red_square: Service is down"
    result = handle_upptime_payload(text)

    assert isinstance(result, WebhookPayload)
    assert result.blocks[1]["text"]["text"] == "🚨 Service Down Alert"


def test_handle_upptime_payload_service_recovered():
    """Test handling of service recovery alerts."""
    text = "🟩 Service is back up and running"
    result = handle_upptime_payload(text)

    assert isinstance(result, WebhookPayload)
    assert result.blocks[1]["text"]["text"] == "✅ Service Recovered"


def test_handle_upptime_payload_service_recovered_large_green_square():
    """Test handling of service recovery with :large_green_square: indicator."""
    text = ":large_green_square: Service is back up"
    result = handle_upptime_payload(text)

    assert isinstance(result, WebhookPayload)
    assert result.blocks[1]["text"]["text"] == "✅ Service Recovered"


def test_handle_upptime_payload_service_degraded():
    """Test handling of service degraded alerts."""
    text = "🟨 Service has degraded performance"
    result = handle_upptime_payload(text)

    assert isinstance(result, WebhookPayload)
    assert result.blocks[1]["text"]["text"] == "⚠️ Service Degraded"


def test_handle_upptime_payload_service_degraded_large_yellow_square():
    """Test handling of service degraded with :large_yellow_square: indicator."""
    text = ":large_yellow_square: Performance issues detected"
    result = handle_upptime_payload(text)

    assert isinstance(result, WebhookPayload)
    assert result.blocks[1]["text"]["text"] == "⚠️ Service Degraded"


def test_handle_upptime_payload_generic_status():
    """Test handling of generic status changes."""
    text = "Some other status update"
    result = handle_upptime_payload(text)

    assert isinstance(result, WebhookPayload)
    assert result.blocks[1]["text"]["text"] == "📈 Web Application Status Changed!"


def test_is_upptime_pattern_red_square():
    """Test pattern detection for red square indicator."""
    text = ":large_red_square: Service is down"
    assert is_upptime_pattern(text) is True


def test_is_upptime_pattern_green_square():
    """Test pattern detection for green square indicator."""
    text = ":large_green_square: Service is back up"
    assert is_upptime_pattern(text) is True


def test_is_upptime_pattern_yellow_square():
    """Test pattern detection for yellow square indicator."""
    text = ":large_yellow_square: Service experiencing degraded performance"
    assert is_upptime_pattern(text) is True


def test_is_upptime_pattern_no_match():
    """Test pattern detection for non-Upptime text."""
    text = "This is just regular text without any indicators"
    assert is_upptime_pattern(text) is False


def test_is_upptime_pattern_emoji_only():
    """Test that emoji alone without status keywords doesn't match."""
    text = ":large_red_square: Just a red square"
    assert is_upptime_pattern(text) is False


def test_is_upptime_pattern_status_only():
    """Test that status keywords alone without emoji don't match."""
    text = "Service is down but no emoji"
    assert is_upptime_pattern(text) is False


def test_is_upptime_pattern_unicode_emojis():
    """Test pattern detection with unicode emojis."""
    assert is_upptime_pattern("🟥 Service is down") is True
    assert is_upptime_pattern("🟩 Service is back up") is True
    assert is_upptime_pattern("🟨 Service experiencing degraded performance") is True


def test_upptime_handler_pattern_configuration():
    """Test the UPPTIME_HANDLER pattern configuration."""
    assert isinstance(UPPTIME_HANDLER, SimpleTextPattern)
    assert UPPTIME_HANDLER.name == "upptime_monitoring"
    assert UPPTIME_HANDLER.match_type == "callable"
    assert (
        UPPTIME_HANDLER.pattern
        == "modules.webhooks.patterns.simple_text.upptime.is_upptime_pattern"
    )
    assert (
        UPPTIME_HANDLER.handler
        == "modules.webhooks.patterns.simple_text.upptime.handle_upptime_payload"
    )
    assert UPPTIME_HANDLER.priority == 10
    assert UPPTIME_HANDLER.enabled is True


def test_register_upptime_pattern():
    """Test registration of the Upptime pattern."""
    # Clear existing handlers
    PATTERN_HANDLERS.clear()

    # Register the pattern
    register_upptime_pattern()

    # Verify it was registered
    assert len(PATTERN_HANDLERS) == 1
    assert PATTERN_HANDLERS[0].name == "upptime_monitoring"
    assert PATTERN_HANDLERS[0].priority == 10


def test_handle_upptime_payload_block_structure():
    """Test that the payload block structure is correct."""
    text = "Test message"
    result = handle_upptime_payload(text)

    # Verify overall structure
    assert hasattr(result, "blocks")
    assert len(result.blocks) == 3

    # Verify spacer block
    spacer_block = result.blocks[0]
    assert spacer_block["type"] == "section"
    assert spacer_block["text"]["type"] == "mrkdwn"
    assert spacer_block["text"]["text"] == " "

    # Verify header block
    header_block = result.blocks[1]
    assert header_block["type"] == "header"
    assert header_block["text"]["type"] == "plain_text"
    assert isinstance(header_block["text"]["text"], str)

    # Verify content block
    content_block = result.blocks[2]
    assert content_block["type"] == "section"
    assert content_block["text"]["type"] == "mrkdwn"
    assert content_block["text"]["text"] == text


def test_handle_upptime_payload_priority_order():
    """Test that the priority order of status detection works correctly."""
    # Test that down status takes precedence
    text_down_and_up = "Service is **down** but also back up"
    result = handle_upptime_payload(text_down_and_up)
    assert result.blocks[1]["text"]["text"] == "🚨 Service Down Alert"

    # Test that up takes precedence over degraded
    text_up_and_degraded = "Service is back up but has degraded performance"
    result = handle_upptime_payload(text_up_and_degraded)
    assert result.blocks[1]["text"]["text"] == "✅ Service Recovered"


def test_handle_upptime_payload_unicode_emojis():
    """Test handling with unicode emojis."""
    assert (
        handle_upptime_payload("🟥 Service is down").blocks[1]["text"]["text"]
        == "🚨 Service Down Alert"
    )
    assert (
        handle_upptime_payload("🟩 Service is back up").blocks[1]["text"]["text"]
        == "✅ Service Recovered"
    )
    assert (
        handle_upptime_payload("🟨 Service experiencing degraded performance").blocks[
            1
        ]["text"]["text"]
        == "⚠️ Service Degraded"
    )


def test_handle_upptime_payload_real_examples():
    """Test with real Upptime message examples."""
    example1 = ":large_green_square: GC Forms - Formulaires GC (https://forms-formulaires.alpha.canada.ca/) is back up"
    result1 = handle_upptime_payload(example1)
    assert result1.blocks[1]["text"]["text"] == "✅ Service Recovered"

    example2 = ":large_red_square: GC Forms - Formulaires GC (https://forms-formulaires.alpha.canada.ca/) is **down** : https://github.com/cds-snc/status-statut/issues/383"
    result2 = handle_upptime_payload(example2)
    assert result2.blocks[1]["text"]["text"] == "🚨 Service Down Alert"


def test_handle_upptime_payload_case_insensitive():
    """Test that status detection is case insensitive."""
    assert (
        handle_upptime_payload("🟥 Service is DOWN").blocks[1]["text"]["text"]
        == "🚨 Service Down Alert"
    )
    assert (
        handle_upptime_payload("🟩 Service is BACK UP").blocks[1]["text"]["text"]
        == "✅ Service Recovered"
    )
    assert (
        handle_upptime_payload("🟨 Service EXPERIENCING DEGRADED PERFORMANCE").blocks[
            1
        ]["text"]["text"]
        == "⚠️ Service Degraded"
    )
