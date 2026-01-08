"""Translation service for dependency injection.

Provides a class-based interface to the i18n system for easier DI and testing.
"""

from typing import Any, Dict, Optional

from infrastructure.i18n.factory import create_translator
from infrastructure.i18n.models import Locale, TranslationKey
from infrastructure.i18n.translator import Translator


class TranslationService:
    """Class-based translation service.

    Wraps the Translator instance with a service interface to support
    dependency injection and easier testing with mocks.

    This is a thin facade - all actual work is delegated to the underlying
    Translator instance created by the factory.

    Usage:
        # Via dependency injection
        from infrastructure.services import TranslationServiceDep

        @router.get("/message")
        def get_message(translation: TranslationServiceDep):
            msg = translation.translate(
                key=TranslationKey.from_string("common.welcome"),
                locale=Locale.EN_US
            )
            return {"message": msg}

        # Direct instantiation
        from infrastructure.i18n import TranslationService

        service = TranslationService()
        message = service.translate(key, locale)
    """

    def __init__(self, translator: Optional[Translator] = None):
        """Initialize translation service.

        Args:
            translator: Optional pre-configured Translator instance.
                       If not provided, creates default via factory.
        """
        self._translator = translator or create_translator()

    def translate(
        self,
        key: TranslationKey,
        locale: Locale,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Retrieve and interpolate a translated message.

        Args:
            key: TranslationKey identifying the message
            locale: Locale to translate to
            variables: Optional dict of variables for interpolation

        Returns:
            Translated and interpolated message string

        Raises:
            KeyError: If key not found in requested locale or fallback locale
        """
        return self._translator.translate_message(key, locale, variables)

    def has_message(self, key: TranslationKey, locale: Locale) -> bool:
        """Check if translation exists for key in locale.

        Args:
            key: TranslationKey to check
            locale: Locale to check

        Returns:
            True if message exists in requested locale, False otherwise
        """
        return self._translator.has_message(key, locale)

    def get_available_locales(self) -> list[Locale]:
        """Get list of loaded locales.

        Returns:
            List of Locale enums that have been loaded
        """
        return self._translator.get_available_locales()

    def load_locale(self, locale: Locale) -> None:
        """Load specific locale from loader.

        Args:
            locale: Locale to load

        Raises:
            FileNotFoundError: If translation files not found
        """
        self._translator.load_locale(locale)

    def load_all(self) -> None:
        """Load all available locales from loader."""
        self._translator.load_all()

    @property
    def translator(self) -> Translator:
        """Access underlying Translator instance.

        Provided for advanced use cases that need direct access
        to the Translator API.

        Returns:
            The underlying Translator instance
        """
        return self._translator
