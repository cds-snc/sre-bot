"""Slack Block Kit response formatter.

Formats responses using Slack's Block Kit format for rich, interactive messages.
See: https://api.slack.com/block-kit
"""

from typing import Any, Dict, List, Optional

from infrastructure.platforms.formatters.base import BaseResponseFormatter


class SlackBlockKitFormatter(BaseResponseFormatter):
    """Formatter for Slack Block Kit JSON responses.

    Converts responses into Slack's Block Kit format with support for:
    - Text sections with markdown
    - Dividers
    - Context blocks
    - Action buttons (future)
    - Rich formatting with emojis

    Example:
        formatter = SlackBlockKitFormatter()
        response = formatter.format_success(
            data={"user_id": "U123"},
            message="User created successfully"
        )
        # Returns Block Kit JSON with success formatting
    """

    def __init__(self, translator=None, locale: str = "en"):
        """Initialize Slack Block Kit formatter.

        Args:
            translator: Optional Translator instance for i18n
            locale: Locale code (default: "en")
        """
        super().__init__(translator=translator, locale=locale)

    def format_success(
        self,
        data: Dict[str, Any],
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format a success response as Slack Block Kit.

        Args:
            data: Success data payload
            message: Optional success message

        Returns:
            Dict containing Slack Block Kit blocks
        """
        blocks = []

        # Header with success emoji
        header_text = f":white_check_mark: {message or 'Success'}"
        blocks.append(self._create_section(header_text))

        # Add data as formatted text if present
        if data:
            data_text = self._format_data_as_text(data)
            if data_text:
                blocks.append({"type": "divider"})
                blocks.append(self._create_section(data_text))

        return {"blocks": blocks}

    def format_error(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format an error response as Slack Block Kit.

        Args:
            message: Error message
            error_code: Optional error code
            details: Optional error details

        Returns:
            Dict containing Slack Block Kit blocks
        """
        blocks = []

        # Header with error emoji
        header_text = f":x: {message}"
        blocks.append(self._create_section(header_text))

        # Add error code if present
        if error_code:
            blocks.append(self._create_context([f"Error Code: `{error_code}`"]))

        # Add details if present
        if details:
            details_text = self._format_data_as_text(details)
            if details_text:
                blocks.append({"type": "divider"})
                blocks.append(self._create_section(details_text))

        return {"blocks": blocks}

    def format_info(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format an info response as Slack Block Kit.

        Args:
            message: Info message
            data: Optional data payload

        Returns:
            Dict containing Slack Block Kit blocks
        """
        blocks = []

        # Header with info emoji
        header_text = f":information_source: {message}"
        blocks.append(self._create_section(header_text))

        # Add data if present
        if data:
            data_text = self._format_data_as_text(data)
            if data_text:
                blocks.append({"type": "divider"})
                blocks.append(self._create_section(data_text))

        return {"blocks": blocks}

    def format_warning(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format a warning response as Slack Block Kit.

        Args:
            message: Warning message
            data: Optional data payload

        Returns:
            Dict containing Slack Block Kit blocks
        """
        blocks = []

        # Header with warning emoji
        header_text = f":warning: {message}"
        blocks.append(self._create_section(header_text))

        # Add data if present
        if data:
            data_text = self._format_data_as_text(data)
            if data_text:
                blocks.append({"type": "divider"})
                blocks.append(self._create_section(data_text))

        return {"blocks": blocks}

    def _create_section(self, text: str) -> Dict[str, Any]:
        """Create a Slack section block with markdown text.

        Args:
            text: Text content for the section

        Returns:
            Section block dict
        """
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text,
            },
        }

    def _create_context(self, elements: List[str]) -> Dict[str, Any]:
        """Create a Slack context block with text elements.

        Args:
            elements: List of text strings for context

        Returns:
            Context block dict
        """
        return {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": elem} for elem in elements],
        }

    def _format_data_as_text(self, data: Dict[str, Any]) -> str:
        """Format data dictionary as markdown text.

        Args:
            data: Data dictionary to format

        Returns:
            Formatted markdown string
        """
        if not data:
            return ""

        lines = []
        for key, value in data.items():
            # Convert snake_case to Title Case for display
            display_key = key.replace("_", " ").title()
            # Format value based on type
            if isinstance(value, (list, dict)):
                # For complex types, just show the type
                display_value = f"_{type(value).__name__}_"
            elif isinstance(value, bool):
                display_value = ":white_check_mark:" if value else ":x:"
            else:
                display_value = f"`{value}`"

            lines.append(f"*{display_key}:* {display_value}")

        return "\n".join(lines)
