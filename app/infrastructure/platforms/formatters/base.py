"""Base response formatter for platform-specific message formats.

All platform-specific formatters (Slack Block Kit, Teams Adaptive Cards, Discord Embeds)
inherit from this base class.
"""

import structlog
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.i18n.translator import Translator


logger = structlog.get_logger()


class BaseResponseFormatter(ABC):
    """Abstract base class for platform-specific response formatters.

    Formatters convert generic data dictionaries into platform-native message formats:
    - Slack: Block Kit JSON
    - Teams: Adaptive Cards JSON
    - Discord: Embed objects

    All formatters must:
    - Implement format_success() for success messages
    - Implement format_error() for error messages
    - Implement format_info() for informational messages
    - Support OperationResult conversion via format_operation_result()
    - Integrate with i18n Translator for multi-locale support

    Attributes:
        _translator: Optional Translator instance for i18n support.
        _locale: Default locale for message formatting.
    """

    def __init__(self, translator: Optional[Translator] = None, locale: str = "en"):
        """Initialize the response formatter.

        Args:
            translator: Optional Translator instance for i18n.
            locale: Default locale for formatting (default: "en").
        """
        self._translator = translator
        self._locale = locale
        self._logger = logger.bind(formatter=self.__class__.__name__)

    @abstractmethod
    def format_success(
        self,
        data: Dict[str, Any],
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format a success response.

        Args:
            data: Data dictionary to format.
            message: Optional success message.

        Returns:
            Platform-specific success message payload.
        """
        pass

    @abstractmethod
    def format_error(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format an error response.

        Args:
            message: Error message to display.
            error_code: Optional error code identifier.
            details: Optional additional error details.

        Returns:
            Platform-specific error message payload.
        """
        pass

    @abstractmethod
    def format_info(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format an informational message.

        Args:
            message: Informational message to display.
            data: Optional additional data to include.

        Returns:
            Platform-specific info message payload.
        """
        pass

    def format_warning(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format a warning message.

        Default implementation delegates to format_info(). Platforms can override
        for custom warning styling.

        Args:
            message: Warning message to display.
            data: Optional additional data to include.

        Returns:
            Platform-specific warning message payload.
        """
        return self.format_info(message=message, data=data)

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

    def translate(self, key: str, **kwargs) -> str:
        """Translate a message key to the current locale.

        Args:
            key: Translation key.
            **kwargs: Substitution variables for the translation.

        Returns:
            Translated string, or key if translator not available.
        """
        if self._translator:
            return self._translator.translate(key, locale=self._locale, **kwargs)
        return key

    def set_locale(self, locale: str) -> None:
        """Set the default locale for formatting.

        Args:
            locale: Locale code (e.g., "en", "fr").
        """
        self._locale = locale

    @property
    def locale(self) -> str:
        """Get the current locale."""
        return self._locale

    def __repr__(self) -> str:
        """String representation of the formatter."""
        return f"{self.__class__.__name__}(locale={self._locale!r})"
