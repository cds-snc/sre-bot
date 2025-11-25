"""i18n system - internationalization and localization framework.

Provides translation management, locale resolution, and variable interpolation
for supporting multiple languages across the application.

Main components:
- models: TranslationKey, Locale, TranslationCatalog, LocaleResolutionContext
- loader: TranslationLoader and YAMLTranslationLoader
- translator: Translator service with message interpolation
- resolvers: LocaleResolver and LanguageNegotiator for locale detection
"""

from infrastructure.i18n.loader import TranslationLoader, YAMLTranslationLoader
from infrastructure.i18n.models import (
    Locale,
    LocaleResolutionContext,
    TranslationCatalog,
    TranslationKey,
)
from infrastructure.i18n.resolvers import LanguageNegotiator, LocaleResolver
from infrastructure.i18n.translator import Translator

__all__ = [
    "Locale",
    "TranslationKey",
    "TranslationCatalog",
    "LocaleResolutionContext",
    "TranslationLoader",
    "YAMLTranslationLoader",
    "Translator",
    "LocaleResolver",
    "LanguageNegotiator",
]
