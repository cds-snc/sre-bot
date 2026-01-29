"""Locale resolution logic for determining user's preferred language.

Provides strategies for resolving the appropriate locale from various sources
(HTTP headers, user preferences, defaults, etc.).
"""

from typing import Optional

import structlog
from infrastructure.i18n.models import Locale, LocaleResolutionContext

logger = structlog.get_logger().bind(component="i18n.resolver")


class LocaleResolver:
    """Resolves user locale from various context sources.

    Implements fallback chain for determining preferred locale:
    1. Explicit request parameter
    2. User profile preference
    3. Accept-Language header (if web context)
    4. Default locale
    """

    def __init__(self, default_locale: Locale = Locale.EN_US):
        """Initialize locale resolver.

        Args:
            default_locale: Fallback locale when no preference found.
        """
        self.default_locale = default_locale
        self.log = logger.bind(default_locale=default_locale.value)

    def resolve_from_header(
        self,
        accept_language: Optional[str],
        supported_locales: Optional[list] = None,
    ) -> Locale:
        """Resolve locale from HTTP Accept-Language header.

        Parses header and returns first supported locale from preference order.

        Args:
            accept_language: Accept-Language header value.
            supported_locales: List of supported locales.

        Returns:
            Resolved Locale, or default if none match.
        """
        if not accept_language:
            return self.default_locale

        supported = supported_locales or [Locale.EN_US, Locale.FR_FR]

        # Parse "en-US,en;q=0.9,fr-FR;q=0.8" -> [(en-US, 1.0), (en, 0.9), (fr-FR, 0.8)]
        preferences = []
        for part in accept_language.split(","):
            lang_range = part.split(";")[0].strip()
            quality = 1.0

            if ";" in part and "q=" in part:
                try:
                    quality = float(part.split("q=")[1])
                except ValueError:
                    quality = 1.0

            preferences.append((lang_range, quality))

        # Sort by quality (descending) and try to match
        for lang_range, _ in sorted(preferences, key=lambda x: x[1], reverse=True):
            # Try exact match
            for locale in supported:
                if locale.value.lower() == lang_range.lower():
                    log = self.log.bind(locale=locale.value)
                    log.info("resolved_from_header")
                    return locale

            # Try language-only match (e.g., "en" matches "en-US")
            lang_code = lang_range.split("-")[0].lower()
            for locale in supported:
                if locale.language.lower() == lang_code:
                    log = self.log.bind(locale=locale.value)
                    log.info("resolved_from_header")
                    return locale

        log = self.log.bind(default=self.default_locale.value)
        log.info("no_matching_locale_in_header")
        return self.default_locale

    def resolve_from_context(
        self,
        context: LocaleResolutionContext,
    ) -> Locale:
        """Resolve locale from LocaleResolutionContext.

        Uses context.resolve() method for fallback chain.

        Args:
            context: Locale resolution context.

        Returns:
            Resolved Locale.
        """
        resolved = context.resolve()
        log = self.log.bind(locale=resolved.value)
        log.info("resolved_from_context")
        return resolved

    def resolve_from_string(self, locale_str: str) -> Locale:
        """Parse and validate locale string.

        Args:
            locale_str: Locale string (e.g., "en-US", "fr-FR").

        Returns:
            Parsed Locale.

        Raises:
            ValueError: If locale_str is not supported.
        """
        try:
            return Locale.from_string(locale_str)
        except ValueError:
            log = self.log.bind(locale_str=locale_str)
            log.warning("invalid_locale_string")
            raise


class LanguageNegotiator:
    """Performs language negotiation for multilingual content.

    Implements RFC 4647 language range matching for complex scenarios
    (e.g., when user requests "pt-BR" but only "pt" is available).
    """

    @staticmethod
    def matches_language(
        requested: str,
        available: str,
        strict: bool = False,
    ) -> bool:
        """Check if available language matches requested language.

        Args:
            requested: Requested language tag (e.g., "en-US").
            available: Available language tag (e.g., "en").
            strict: If True, requires exact match. If False, allows language-only match.

        Returns:
            True if languages match.
        """
        if requested.lower() == available.lower():
            return True

        if strict:
            return False

        # Language-only match (e.g., "en-US" matches "en")
        requested_lang = requested.split("-")[0].lower()
        available_lang = available.split("-")[0].lower()
        return requested_lang == available_lang

    @staticmethod
    def find_best_match(
        requested: list,
        available: list,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """Find best matching language from available options.

        Args:
            requested: List of requested language tags in preference order.
            available: List of available language tags.
            default: Default if no match found.

        Returns:
            Best matching language from available, or default if no match.
        """
        for req_lang in requested:
            # Try exact match first
            for avail_lang in available:
                if LanguageNegotiator.matches_language(
                    req_lang, avail_lang, strict=True
                ):
                    return avail_lang

            # Try language-only match
            for avail_lang in available:
                if LanguageNegotiator.matches_language(
                    req_lang, avail_lang, strict=False
                ):
                    return avail_lang

        return default
