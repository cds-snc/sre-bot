"""Translation service for retrieving and interpolating translated messages.

Core component for i18n that integrates with infrastructure.events for notifications.
"""

import re
from typing import Any, Dict, Optional

from core.logging import get_module_logger
from infrastructure.i18n.loader import TranslationLoader
from infrastructure.i18n.models import Locale, TranslationCatalog, TranslationKey

logger = get_module_logger()


class Translator:
    """Service for translating messages with variable interpolation.

    Manages catalogs for multiple locales and provides
    translate_message() with support for variable substitution.

    Attributes:
        loader: TranslationLoader for loading translation files.
        catalogs: Cache of loaded TranslationCatalogs by locale.
        fallback_locale: Locale to use when key not found.
    """

    def __init__(
        self,
        loader: TranslationLoader,
        fallback_locale: Locale = Locale.EN_US,
    ):
        """Initialize Translator.

        Args:
            loader: TranslationLoader instance for loading translations.
            fallback_locale: Locale to use when key not found (default: en-US).
        """
        self.loader = loader
        self.fallback_locale = fallback_locale
        self.catalogs: Dict[Locale, TranslationCatalog] = {}
        logger.info("initialized_translator", fallback_locale=fallback_locale.value)

    def load_all(self) -> None:
        """Load all available locales from loader."""
        self.catalogs = self.loader.load_all()
        logger.info("loaded_all_translations", locale_count=len(self.catalogs))

    def load_locale(self, locale: Locale) -> None:
        """Load specific locale from loader.

        Args:
            locale: Locale to load.

        Raises:
            FileNotFoundError: If translation files not found.
        """
        self.catalogs[locale] = self.loader.load(locale)
        logger.info("loaded_locale_translations", locale=locale.value)

    def translate_message(
        self,
        key: TranslationKey,
        locale: Locale,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Retrieve and interpolate a translated message.

        Performs variable substitution using {{variable_name}} syntax.
        Falls back to fallback_locale if key not found in requested locale.

        Args:
            key: TranslationKey identifying the message.
            locale: Locale to translate to.
            variables: Optional dict of variables for interpolation.

        Returns:
            Translated and interpolated message string.

        Raises:
            KeyError: If key not found in requested locale or fallback locale.
        """
        variables = variables or {}

        # Try to get message from requested locale
        catalog = self.catalogs.get(locale)
        message = catalog.get_message(key) if catalog else None

        # Fall back to fallback locale if needed
        if not message and locale != self.fallback_locale:
            fallback_catalog = self.catalogs.get(self.fallback_locale)
            message = fallback_catalog.get_message(key) if fallback_catalog else None

            if message:
                logger.info(
                    "used_fallback_translation",
                    key=str(key),
                    requested_locale=locale.value,
                    fallback_locale=self.fallback_locale.value,
                )

        if not message:
            logger.error(
                "translation_not_found",
                key=str(key),
                locale=locale.value,
                fallback_locale=self.fallback_locale.value,
            )
            raise KeyError(
                f"Translation not found for key {key} in {locale.value} or fallback {self.fallback_locale.value}"
            )

        # Interpolate variables (always call to validate required variables)
        message = self._interpolate(message, variables)

        return message

    def has_message(self, key: TranslationKey, locale: Locale) -> bool:
        """Check if translation exists for key in locale.

        Args:
            key: TranslationKey to check.
            locale: Locale to check.

        Returns:
            True if message exists in requested locale, False otherwise.
        """
        catalog = self.catalogs.get(locale)
        return catalog.has_message(key) if catalog else False

    def get_available_locales(self) -> list:
        """Get list of loaded locales.

        Returns:
            List of Locale enums that have been loaded.
        """
        return list(self.catalogs.keys())

    def _interpolate(self, message: str, variables: Dict[str, Any]) -> str:
        """Perform variable interpolation in message string.

        Replaces {{variable_name}} with corresponding value from variables dict.

        Args:
            message: Message string with {{variable}} placeholders.
            variables: Dict of variable name -> value.

        Returns:
            Message with variables interpolated.

        Raises:
            ValueError: If variable not found in variables dict.
        """
        # Support both double-brace ({{var}}) and single-brace ({var}) placeholders.
        # Collect unique variable names from both patterns in order to validate
        # required variables exist before performing replacements.
        double_pattern = r"\{\{(\w+)\}\}"
        single_pattern = r"\{(\w+)\}"

        double_matches = re.findall(double_pattern, message)
        single_matches = re.findall(single_pattern, message)

        # We avoid double-counting variables that appear in both patterns
        all_vars = []
        for m in double_matches + single_matches:
            if m not in all_vars:
                all_vars.append(m)

        for var_name in all_vars:
            if var_name not in variables:
                logger.error(
                    "missing_interpolation_variable",
                    variable=var_name,
                    available_variables=list(variables.keys()),
                )
                raise ValueError(f"Missing interpolation variable: {var_name}")

        # Perform replacements. Replace double-brace patterns first to preserve
        # any intention where both syntaxes might be present.
        for var_name in double_matches:
            value = variables[var_name]
            message = message.replace(f"{{{{{var_name}}}}}", str(value))

        for var_name in single_matches:
            value = variables[var_name]
            message = message.replace(f"{{{var_name}}}", str(value))

        return message

    def get_catalog(self, locale: Locale) -> Optional[TranslationCatalog]:
        """Get complete catalog for a locale.

        Args:
            locale: Locale to retrieve catalog for.

        Returns:
            TranslationCatalog or None if not loaded.
        """
        return self.catalogs.get(locale)

    def reload(self) -> None:
        """Reload all translations from loader."""
        self.catalogs.clear()
        self.load_all()
        logger.info("reloaded_all_translations")
