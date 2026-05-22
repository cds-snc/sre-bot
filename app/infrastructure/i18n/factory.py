"""Factory functions for creating i18n components.

Provides convenience functions for initializing translators with default
configurations suitable for the application.
"""

from functools import cache
from pathlib import Path
from typing import Any

import structlog

from infrastructure.i18n.loader import YAMLTranslationLoader
from infrastructure.i18n.models import Locale, TranslationKey
from infrastructure.i18n.service import TranslationService
from infrastructure.i18n.translator import Translator

logger = structlog.get_logger()


def create_translator(
    translations_dir: Path | None = None,
    fallback_locale: Locale = Locale.EN_US,
    use_cache: bool = True,
    preload: bool = True,
) -> Translator:
    """Create and configure a Translator instance.

    If no translations_dir is provided, automatically discovers the default
    locales directory from the application structure.

    Args:
        translations_dir: Path to YAML translation files (default: auto-discover app/locales)
        fallback_locale: Locale to use when translations not found (default: en-US)
        use_cache: Whether loader should cache parsed YAML (default: True)
        preload: Whether to load all locales immediately (default: True)

    Returns:
        Translator: Configured translator instance

    Raises:
        ValueError: If translations_dir does not exist

    Usage:
        # Use defaults (auto-discover app/locales, preload all)
        translator = create_translator()

        # Custom translations directory
        translator = create_translator(translations_dir=Path("/custom/locales"))

        # Lazy loading
        translator = create_translator(preload=False)
        translator.load_locale(Locale.EN_US)
    """
    if translations_dir is None:
        # Auto-discover: this file is at .../app/infrastructure/i18n/factory.py
        # Navigate up to app/, then into locales/
        app_root = Path(__file__).resolve().parents[2]
        translations_dir = app_root / "locales"

    loader = YAMLTranslationLoader(
        translations_dir=translations_dir,
        use_cache=use_cache,
    )
    translator = Translator(loader=loader, fallback_locale=fallback_locale)

    if preload:
        translator.load_all()
        log = logger.bind(
            translations_dir=str(translations_dir),
            locale_count=len(translator.get_available_locales()),
        )
        log.info("translator_created_with_preload")
    else:
        log = logger.bind(translations_dir=str(translations_dir))
        log.info("translator_created_lazy")

    return translator


@cache
def get_translation_service() -> TranslationService:
    """Get application-scoped translation service singleton.

    Returns a TranslationService instance with pre-configured Translator
    that has all YAML catalogs loaded from the default locales directory.
    """
    # TranslationService doesn't need settings - uses factory internally
    translator = create_translator()
    return TranslationService(translator=translator)


@cache
def t(key: str, locale: str, fallback: str = "", **variables: Any) -> str:
    """Translate a key safely, designed for use in command handlers and feature packages.

    Wraps the application-scoped translation singleton with a fallback so callers
    never have to guard against uninitialized state or missing keys.

    Args:
        key: Dot-separated translation key (e.g. "geolocate.result.city_label").
        locale: Locale string such as "en-US" or "fr-FR".
        fallback: Returned as-is when the key is missing or the service is not yet ready.
        **variables: Interpolation variables for ``{{variable}}`` placeholders.

    Returns:
        Translated and interpolated string, or *fallback* on any error.
    """
    try:
        return get_translation_service().translate(
            key=TranslationKey.from_string(key),
            locale=Locale.from_string(locale),
            variables=variables or None,
        )
    except Exception:
        return fallback
