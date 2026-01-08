"""Factory functions for creating i18n components.

Provides convenience functions for initializing translators with default
configurations suitable for the application.
"""

from pathlib import Path

import structlog
from infrastructure.i18n.loader import YAMLTranslationLoader
from infrastructure.i18n.translator import Translator
from infrastructure.i18n.models import Locale

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
        logger.info(
            "translator_created_with_preload",
            translations_dir=str(translations_dir),
            locale_count=len(translator.get_available_locales()),
        )
    else:
        logger.info(
            "translator_created_lazy",
            translations_dir=str(translations_dir),
        )

    return translator
