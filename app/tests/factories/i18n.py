"""Test data factories for i18n system testing.

Provides deterministic test data builders for:
- TranslationKey
- TranslationCatalog
- LocaleResolutionContext
- Translation data structures
"""

from typing import Optional

from infrastructure.i18n import (
    Locale,
    LocaleResolutionContext,
    TranslationCatalog,
    TranslationKey,
)


def make_translation_key(
    namespace: str = "incident", message_key: str = "created"
) -> TranslationKey:
    """Create a TranslationKey instance.

    Args:
        namespace: Namespace (e.g., "incident", "role").
        message_key: Message key within namespace.

    Returns:
        TranslationKey instance.
    """
    return TranslationKey(namespace=namespace, message_key=message_key)


def make_translation_catalog(
    locale: Locale = Locale.EN_US,
    messages: dict = None,
    loaded_at: str = None,
) -> TranslationCatalog:
    """Create a TranslationCatalog instance.

    Args:
        locale: Locale for the catalog.
        messages: Nested dict {namespace: {key: message}}.
        loaded_at: ISO 8601 timestamp.

    Returns:
        TranslationCatalog instance.
    """
    if messages is None:
        messages = {
            "incident": {
                "created": "Incident created",
                "resolved": "Incident resolved",
            },
            "role": {
                "created": "Role created",
            },
        }

    return TranslationCatalog(
        locale=locale,
        messages=messages,
        loaded_at=loaded_at or "2024-01-01T00:00:00Z",
    )


def make_locale_resolution_context(
    requested_locale: Optional[Locale] = None,
    user_locale: Optional[Locale] = None,
    default_locale: Locale = Locale.EN_US,
    supported_locales: Optional[list] = None,
) -> LocaleResolutionContext:
    """Create a LocaleResolutionContext instance.

    Args:
        requested_locale: User-requested locale.
        user_locale: User's profile locale preference.
        default_locale: System default locale.
        supported_locales: List of supported locales.

    Returns:
        LocaleResolutionContext instance.
    """
    if supported_locales is None:
        supported_locales = [Locale.EN_US, Locale.FR_FR]

    return LocaleResolutionContext(
        requested_locale=requested_locale,
        user_locale=user_locale,
        default_locale=default_locale,
        supported_locales=supported_locales,
    )
