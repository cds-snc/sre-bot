"""Slack Block Kit response formatter.

Formats responses using Slack's Block Kit format for rich, interactive messages.
See: https://api.slack.com/block-kit
"""

from typing import Any, Dict, List, Optional
from structlog import get_logger
from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.i18n import Locale, TranslationKey, TranslationService

logger = get_logger(__name__)


class SlackBlockKitFormatter:
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

    def __init__(
        self,
        translation_service: Optional[TranslationService] = None,
        locale: str = "en-US",
    ):
        """Initialize Slack Block Kit formatter.

        Args:
            translation_service: Optional TranslationService instance for i18n
            locale: Locale code (default: "en-US")
        """
        self._translation_service = translation_service
        self._locale_str = locale
        self._logger = logger.bind(formatter=self.__class__.__name__)

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

    def format_operation_result(self, result: OperationResult) -> Dict[str, Any]:
        """Convert an OperationResult to platform-specific format.

        Routes to format_success() or format_error() based on result status.

        Args:
            result: OperationResult to format.

        Returns:
            Platform-specific message payload.
        """
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

    def translate(
        self,
        key: str,
        variables: Optional[Dict[str, Any]] = None,
        fallback: Optional[str] = None,
    ) -> str:
        """Translate a message key to the current locale.

        Uses the injected TranslationService to translate message keys.
        If no translation service is available, returns the fallback or key.

        Args:
            key: Translation key (e.g., "platforms.slack.success")
            variables: Optional substitution variables for the translation
            fallback: Optional fallback string if translation not found

        Returns:
            Translated string, or fallback, or key if translation unavailable

        Example:
            >>> formatter = SlackBlockKitFormatter(translation_service=service)
            >>> msg = formatter.translate(
            ...     "platforms.success_message",
            ...     variables={"action": "created"},
            ...     fallback="Operation completed successfully"
            ... )
        """
        if self._translation_service is None:
            return fallback or key

        try:
            translation_key = TranslationKey.from_string(key)
            locale = Locale.from_string(self._locale_str)
            return self._translation_service.translate(
                key=translation_key, locale=locale, variables=variables
            )
        except (KeyError, ValueError) as e:
            self._logger.warning(
                "translation_failed", key=key, locale=self._locale_str, error=str(e)
            )
            return fallback or key

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

    def set_locale(self, locale: str) -> None:
        """Set the default locale for formatting.

        Args:
            locale: Locale code (e.g., "en", "fr", "en-US")
        """
        self._locale_str = locale

    @property
    def locale(self) -> str:
        """Get the current locale.

        Returns:
            String representing current locale
        """
        return self._locale_str

    @property
    def has_translation_service(self) -> bool:
        """Check if formatter has translation service configured.

        Returns:
            True if translation service is available
        """
        return self._translation_service is not None

    def __repr__(self) -> str:
        """String representation of the formatter."""
        return f"{self.__class__.__name__}(locale={self._locale_str!r})"
