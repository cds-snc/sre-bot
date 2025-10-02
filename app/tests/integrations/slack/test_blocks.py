"""Tests for Slack block utilities."""

from integrations.slack.blocks import (
    create_context_block,
    create_divider_block,
    create_header_block,
    create_section_block,
    validate_blocks,
)


def test_validate_blocks():
    """Test the validate_blocks function with various block structures."""
    # Valid blocks
    valid_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}},
        {"type": "divider"},
        {"type": "header", "text": {"type": "plain_text", "text": "Header"}},
        {
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Click"}}
            ],
        },
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "Context text"}]},
    ]
    assert validate_blocks(valid_blocks) is True

    # Invalid blocks - not a list
    assert validate_blocks("not a list") is False

    # Invalid blocks - block not a dict
    assert validate_blocks(["not a dict"]) is False

    # Invalid blocks - missing type
    assert validate_blocks([{"text": "no type"}]) is False

    # Invalid blocks - section missing text
    assert validate_blocks([{"type": "section"}]) is False

    # Invalid blocks - header missing text
    assert validate_blocks([{"type": "header"}]) is False

    # Invalid blocks - divider with extra fields
    assert validate_blocks([{"type": "divider", "extra": "field"}]) is False

    # Invalid blocks - actions missing elements
    assert validate_blocks([{"type": "actions"}]) is False

    # Invalid blocks - context missing elements
    assert validate_blocks([{"type": "context"}]) is False

    # Empty list is valid
    assert validate_blocks([]) is True


def test_create_section_block():
    """Test section block creation."""
    # Default markdown
    section = create_section_block("Hello *world*")
    assert section == {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "Hello *world*"},
    }

    # Plain text
    section_plain = create_section_block("Hello world", "plain_text")
    assert section_plain == {
        "type": "section",
        "text": {"type": "plain_text", "text": "Hello world"},
    }


def test_create_header_block():
    """Test header block creation."""
    header = create_header_block("My Header")
    assert header == {
        "type": "header",
        "text": {"type": "plain_text", "text": "My Header"},
    }


def test_create_divider_block():
    """Test divider block creation."""
    divider = create_divider_block()
    assert divider == {"type": "divider"}


def test_create_context_block():
    """Test context block creation."""
    elements = [{"type": "mrkdwn", "text": "Context info"}]
    context = create_context_block(elements)
    assert context == {"type": "context", "elements": elements}


def test_created_blocks_are_valid():
    """Test that all created blocks pass validation."""
    blocks = [
        create_section_block("Test section"),
        create_header_block("Test header"),
        create_divider_block(),
        create_context_block([{"type": "mrkdwn", "text": "Context"}]),
    ]

    assert validate_blocks(blocks) is True
