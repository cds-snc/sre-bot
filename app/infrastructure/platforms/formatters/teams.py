"""Microsoft Teams Adaptive Cards response formatter.

Formats responses as Teams Adaptive Cards with proper schema, styling, and actions.

Adaptive Cards Documentation:
- Schema: https://adaptivecards.io/schemas/adaptive-card.json
- Designer: https://adaptivecards.io/designer/
- Version: 1.4 (Teams compatibility)

Example:
    >>> from infrastructure.platforms.formatters.teams import TeamsAdaptiveCardsFormatter
    >>>
    >>> formatter = TeamsAdaptiveCardsFormatter()
    >>> card = formatter.format_success(data={"user": "alice"}, message="User added")
    >>> print(card["type"])
    message
"""

import structlog
from typing import Any, Dict, Optional

from infrastructure.platforms.formatters.base import BaseResponseFormatter

logger = structlog.get_logger()


class TeamsAdaptiveCardsFormatter(BaseResponseFormatter):
    """Format responses as Microsoft Teams Adaptive Cards.

    Converts standard data dictionaries into Teams-compatible Adaptive Card
    JSON structures with proper styling, colors, and action buttons.

    Attributes:
        SCHEMA_VERSION: Adaptive Cards schema version (1.4 for Teams compatibility)
    """

    SCHEMA_VERSION = "1.4"

    def __init__(self, translation_service=None, locale: str = "en-US"):
        """Initialize Teams Adaptive Cards formatter.

        Args:
            translation_service: Optional TranslationService instance for i18n
            locale: Locale code (default: "en-US")
        """
        super().__init__(translation_service=translation_service, locale=locale)

    def format_success(
        self,
        data: Dict[str, Any],
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format a success response as Adaptive Card.

        Args:
            data: Success data payload
            message: Optional success message

        Returns:
            Teams Adaptive Card with success styling (green accent)
        """
        log = logger.bind(operation="format_success", message=message)
        log.debug("formatting_success_response")

        card_body: list[Dict[str, Any]] = [
            {
                "type": "TextBlock",
                "text": "✅ Success",
                "weight": "Bolder",
                "size": "Large",
                "color": "Good",
            },
            {
                "type": "TextBlock",
                "text": message or "Operation successful",
                "wrap": True,
            },
        ]

        # Add data fields as FactSet if available
        if data:
            facts = [
                {"title": str(key), "value": str(value)} for key, value in data.items()
            ]
            card_body.append({"type": "FactSet", "facts": facts})

        card = self._build_adaptive_card(
            body=card_body, accent_color="#28A745"  # Green
        )

        log.info("success_response_formatted", has_data=bool(data))
        return card

    def format_error(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format an error response as Adaptive Card.

        Args:
            message: Error message to display
            error_code: Optional error code identifier
            details: Optional additional error details

        Returns:
            Teams Adaptive Card with error styling (red accent)
        """
        log = logger.bind(
            operation="format_error",
            message=message,
            error_code=error_code,
        )
        log.debug("formatting_error_response")

        card_body: list[Dict[str, Any]] = [
            {
                "type": "TextBlock",
                "text": "❌ Error",
                "weight": "Bolder",
                "size": "Large",
                "color": "Attention",
            },
            {"type": "TextBlock", "text": message, "wrap": True},
        ]

        # Add error code if available
        if error_code:
            card_body.append(
                {
                    "type": "TextBlock",
                    "text": f"Error Code: {error_code}",
                    "size": "Small",
                    "isSubtle": True,
                }
            )

        # Add details as FactSet if available
        if details:
            facts = [
                {"title": str(key), "value": str(value)}
                for key, value in details.items()
            ]
            card_body.append({"type": "FactSet", "facts": facts})

        card = self._build_adaptive_card(body=card_body, accent_color="#DC3545")  # Red

        log.info("error_response_formatted", error_code=error_code)
        return card

    def format_info(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format an informational message as Adaptive Card.

        Args:
            message: Information message text
            data: Optional key-value data to display

        Returns:
            Teams Adaptive Card with info styling (blue accent)
        """
        log = logger.bind(operation="format_info", message=message)
        log.debug("formatting_info_message")

        card_body: list[Dict[str, Any]] = [
            {
                "type": "TextBlock",
                "text": "ℹ️ Info",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Default",
            },
            {"type": "TextBlock", "text": message, "wrap": True},
        ]

        # Add data fields as FactSet if provided
        if data:
            facts = [
                {"title": str(key), "value": str(value)} for key, value in data.items()
            ]
            card_body.append({"type": "FactSet", "facts": facts})

        card = self._build_adaptive_card(body=card_body, accent_color="#17A2B8")  # Blue

        log.info("info_message_formatted", has_data=bool(data))
        return card

    def format_warning(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format a warning message as Adaptive Card.

        Args:
            message: Warning message text
            data: Optional key-value data to display

        Returns:
            Teams Adaptive Card with warning styling (yellow accent)
        """
        log = logger.bind(operation="format_warning", message=message)
        log.debug("formatting_warning_message")

        card_body: list[Dict[str, Any]] = [
            {
                "type": "TextBlock",
                "text": "⚠️ Warning",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Warning",
            },
            {"type": "TextBlock", "text": message, "wrap": True},
        ]

        # Add data fields as FactSet if provided
        if data:
            facts = [
                {"title": str(key), "value": str(value)} for key, value in data.items()
            ]
            card_body.append({"type": "FactSet", "facts": facts})

        card = self._build_adaptive_card(
            body=card_body, accent_color="#FFC107"  # Yellow
        )

        log.info("warning_message_formatted", has_data=bool(data))
        return card

    def _build_adaptive_card(
        self,
        body: list[Dict[str, Any]],
        accent_color: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build complete Adaptive Card structure.

        Args:
            body: List of card body elements (TextBlock, FactSet, etc.)
            accent_color: Optional hex color for card accent (#RRGGBB)

        Returns:
            Complete Teams message with Adaptive Card attachment
        """
        content: Dict[str, Any] = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": self.SCHEMA_VERSION,
            "body": body,
        }

        # Add accent color if provided
        if accent_color:
            content["accentColor"] = accent_color

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": content,
                }
            ],
        }
