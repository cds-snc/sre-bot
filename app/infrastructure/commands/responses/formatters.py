"""Response formatters for platform-specific rendering."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from infrastructure.commands.responses.models import (
    Card,
    ErrorMessage,
    SuccessMessage,
)


class ResponseFormatter(ABC):
    """Base class for platform-specific response formatters.

    Subclasses implement platform-specific formatting logic for
    converting platform-agnostic response models into native platform formats.

    Example:
        class SlackResponseFormatter(ResponseFormatter):
            def format_card(self, card: Card) -> Dict[str, Any]:
                return {"blocks": [...]}  # Slack Block Kit format
    """

    @abstractmethod
    def format_text(self, text: str) -> Dict[str, Any]:
        """Format plain text message.

        Args:
            text: Plain text message to format.

        Returns:
            Platform-specific message format as dictionary.
        """
        pass

    @abstractmethod
    def format_card(self, card: Card) -> Dict[str, Any]:
        """Format card/embed message.

        Args:
            card: Platform-agnostic card representation.

        Returns:
            Platform-specific card format as dictionary.
        """
        pass

    @abstractmethod
    def format_error(self, error: ErrorMessage) -> Dict[str, Any]:
        """Format error message.

        Args:
            error: Platform-agnostic error representation.

        Returns:
            Platform-specific error format as dictionary.
        """
        pass

    @abstractmethod
    def format_success(self, success: SuccessMessage) -> Dict[str, Any]:
        """Format success message.

        Args:
            success: Platform-agnostic success representation.

        Returns:
            Platform-specific success format as dictionary.
        """
        pass
