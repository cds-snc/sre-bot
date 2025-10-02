"""Slack Block Kit utilities and validation.

This module provides utilities for working with Slack Block Kit elements,
including validation and construction helpers.
"""

from typing import Dict, List


def validate_blocks(blocks: List[Dict]) -> bool:
    """
    Validate that the provided blocks are valid Slack Block Kit structures.

    This performs basic structural validation to catch common errors before
    sending blocks to the Slack API. It's not exhaustive but covers the most
    common block types and their required fields.

    Args:
        blocks: List of Slack block dictionaries to validate

    Returns:
        bool: True if blocks are structurally valid, False otherwise

    Examples:
        >>> blocks = [
        ...     {"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}},
        ...     {"type": "divider"}
        ... ]
        >>> validate_blocks(blocks)
        True

        >>> invalid_blocks = [{"text": "missing type"}]
        >>> validate_blocks(invalid_blocks)
        False
    """
    if not isinstance(blocks, list):
        return False

    for block in blocks:
        if not isinstance(block, dict):
            return False

        if "type" not in block:
            return False

        # Basic validation for common block types
        block_type = block.get("type")

        # Section and header blocks require text
        if block_type in ["section", "header"] and "text" not in block:
            return False

        # Divider blocks should be minimal
        if block_type == "divider" and len(block) > 1:
            return False

        # Actions blocks require elements
        if block_type == "actions" and "elements" not in block:
            return False

        # Context blocks require elements
        if block_type == "context" and "elements" not in block:
            return False

    return True


def create_section_block(text: str, text_type: str = "mrkdwn") -> Dict:
    """
    Create a section block with the given text.

    Args:
        text: The text content for the section
        text_type: The text type, either 'mrkdwn' or 'plain_text'

    Returns:
        Dict: A valid Slack section block
    """
    return {"type": "section", "text": {"type": text_type, "text": text}}


def create_header_block(text: str) -> Dict:
    """
    Create a header block with the given text.

    Args:
        text: The text content for the header

    Returns:
        Dict: A valid Slack header block
    """
    return {"type": "header", "text": {"type": "plain_text", "text": text}}


def create_divider_block() -> Dict:
    """
    Create a divider block.

    Returns:
        Dict: A valid Slack divider block
    """
    return {"type": "divider"}


def create_context_block(elements: List[Dict]) -> Dict:
    """
    Create a context block with the given elements.

    Args:
        elements: List of text or image elements for the context

    Returns:
        Dict: A valid Slack context block
    """
    return {"type": "context", "elements": elements}
