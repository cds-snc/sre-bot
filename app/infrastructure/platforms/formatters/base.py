"""Base response formatter for platform-specific message formats.

All platform-specific formatters (Slack Block Kit, Teams Adaptive Cards, Discord Embeds)
inherit from this base class.
"""

import structlog
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.i18n.models import Locale, TranslationKey


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
    - Integrate with TranslationService for multi-locale support

    Attributes:
        _translation_service: Optional TranslationService instance for i18n support.
        _locale: Default locale for message formatting.
    """

    def __init__(self, translation_service=None, locale: str = "en-US"):
        """Initialize the response formatter.

        Args:
            translation_service: Optional TranslationService instance for i18n.
            locale: Default locale for formatting (default: "en-US").
        """
        self._translation_service = translation_service
        # Store locale as string for flexibility, convert only when needed
        self._locale_str = locale
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
        if not self._translation_service:
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
