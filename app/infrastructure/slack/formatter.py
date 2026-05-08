"""Slack Block Kit response formatter."""

from typing import Any, Dict, List, Optional

from infrastructure.operations import OperationResult, OperationStatus


class SlackBlockKitFormatter:
    """Formats responses using Slack Block Kit JSON.

    Converts data into Slack's Block Kit format for rich, interactive messages.
    """

    def __init__(self, translation_service=None, locale: str = "en-US"):
        """Initialize formatter.

        Args:
            translation_service: Optional for i18n support
            locale: Locale code (default: "en-US")
        """
        self._translation_service = translation_service
        self._locale_str = locale

    def format_success(
        self,
        data: Dict[str, Any],
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format a success response as Block Kit."""
        blocks = []

        header_text = f":white_check_mark: {message or 'Success'}"
        blocks.append(self._create_section(header_text))

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
        """Format an error response as Block Kit."""
        blocks = []

        header_text = f":x: {message}"
        blocks.append(self._create_section(header_text))

        if error_code:
            blocks.append(self._create_context([f"Error Code: `{error_code}`"]))

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
        """Format an info response as Block Kit."""
        blocks = []

        header_text = f":information_source: {message}"
        blocks.append(self._create_section(header_text))

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
        """Format a warning response as Block Kit."""
        blocks = []

        header_text = f":warning: {message}"
        blocks.append(self._create_section(header_text))

        if data:
            data_text = self._format_data_as_text(data)
            if data_text:
                blocks.append({"type": "divider"})
                blocks.append(self._create_section(data_text))

        return {"blocks": blocks}

    def format_operation_result(self, result: OperationResult) -> Dict[str, Any]:
        """Convert OperationResult to Block Kit format."""
        if result.status == OperationStatus.SUCCESS:
            return self.format_success(
                data=result.data or {},
                message=result.message,
            )
        else:
            return self.format_error(
                message=result.message or "An error occurred",
                error_code=result.error_code,
                details=result.data,
            )

    def _create_section(self, text: str) -> Dict[str, Any]:
        """Create a section block with markdown text."""
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text,
            },
        }

    def _create_context(self, elements: List[str]) -> Dict[str, Any]:
        """Create a context block with text elements."""
        return {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": elem} for elem in elements],
        }

    def _format_data_as_text(self, data: Dict[str, Any]) -> str:
        """Format data dictionary as markdown text."""
        if not data:
            return ""

        lines = []
        for key, value in data.items():
            display_key = key.replace("_", " ").title()
            if isinstance(value, (list, dict)):
                display_value = f"_{type(value).__name__}_"
            elif isinstance(value, bool):
                display_value = ":white_check_mark:" if value else ":x:"
            else:
                display_value = f"`{value}`"

            lines.append(f"*{display_key}:* {display_value}")

        return "\n".join(lines)

    def set_locale(self, locale: str) -> None:
        """Set locale for formatting."""
        self._locale_str = locale

    @property
    def locale(self) -> str:
        """Get current locale."""
        return self._locale_str

    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(locale={self._locale_str!r})"


__all__ = ["SlackBlockKitFormatter"]
