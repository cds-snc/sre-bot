"""Slack-specific response formatter using Block Kit."""

from typing import Any, Dict, List

from infrastructure.commands.responses.formatters import ResponseFormatter
from infrastructure.commands.responses.models import (
    ButtonStyle,
    Card,
    ErrorMessage,
    SuccessMessage,
)


class SlackResponseFormatter(ResponseFormatter):
    """Formatter for Slack Block Kit responses.

    Converts platform-agnostic response models to Slack Block Kit format.

    Reference: https://api.slack.com/block-kit
    """

    def format_text(self, text: str) -> Dict[str, Any]:
        """Format plain text message for Slack.

        Args:
            text: Plain text message.

        Returns:
            Slack message dict with text key.
        """
        return {"text": text}

    def format_card(self, card: Card) -> Dict[str, Any]:
        """Format card as Slack blocks.

        Args:
            card: Platform-agnostic card.

        Returns:
            Slack message with blocks array.
        """
        blocks: List[Dict[str, Any]] = []

        # Header section
        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": card.title},
            }
        )

        # Main text section
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": card.text},
            }
        )

        # Fields section (if any)
        if card.fields:
            fields_list = []
            for field in card.fields:
                fields_list.append(
                    {
                        "type": "mrkdwn",
                        "text": f"*{field.title}*\n{field.value}",
                    }
                )

            blocks.append(
                {
                    "type": "section",
                    "fields": fields_list,
                }
            )

        # Image (if any)
        if card.image_url:
            blocks.append(
                {
                    "type": "image",
                    "image_url": card.image_url,
                    "alt_text": card.title,
                }
            )

        # Buttons section (if any)
        if card.buttons:
            elements = []
            for button in card.buttons:
                button_style = self._map_button_style(button.style)
                button_elem = {
                    "type": "button",
                    "text": {"type": "plain_text", "text": button.text},
                    "action_id": button.action_id,
                }
                if button_style:
                    button_elem["style"] = button_style
                if button.value:
                    button_elem["value"] = button.value

                elements.append(button_elem)

            blocks.append({"type": "actions", "elements": elements})

        # Footer context (if any)
        if card.footer:
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": card.footer}],
                }
            )

        # Divider for visual separation
        blocks.append({"type": "divider"})

        return {
            "blocks": blocks,
            "text": card.title,  # Fallback text for notifications
        }

    def format_error(self, error: ErrorMessage) -> Dict[str, Any]:
        """Format error message for Slack.

        Args:
            error: Platform-agnostic error.

        Returns:
            Slack message with error formatting.
        """
        blocks: List[Dict[str, Any]] = []

        # Error header
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f":x: *Error*\n{error.message}"},
            }
        )

        # Error details (if any)
        if error.details:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"```{error.details}```"},
                }
            )

        # Error code context (if any)
        if error.error_code:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"Error Code: `{error.error_code}`"}
                    ],
                }
            )

        return {
            "blocks": blocks,
            "text": f":x: {error.message}",
        }

    def format_success(self, success: SuccessMessage) -> Dict[str, Any]:
        """Format success message for Slack.

        Args:
            success: Platform-agnostic success message.

        Returns:
            Slack message with success formatting.
        """
        blocks: List[Dict[str, Any]] = []

        # Success message
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":white_check_mark: {success.message}",
                },
            }
        )

        # Success details (if any)
        if success.details:
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": success.details}],
                }
            )

        return {
            "blocks": blocks,
            "text": f":white_check_mark: {success.message}",
        }

    def _map_button_style(self, style: ButtonStyle) -> str:
        """Map platform-agnostic button style to Slack style.

        Args:
            style: Platform-agnostic button style.

        Returns:
            Slack button style string or empty string for default.
        """
        mapping = {
            ButtonStyle.PRIMARY: "primary",
            ButtonStyle.DANGER: "danger",
            ButtonStyle.DEFAULT: "",
        }
        return mapping.get(style, "")
