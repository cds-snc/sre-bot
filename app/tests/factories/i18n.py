"""Test data factories for i18n system testing.

Provides deterministic test data builders for:
- TranslationKey
- TranslationCatalog
- LocaleResolutionContext
- Translation data structures
"""

from collections.abc import Callable

from infrastructure.i18n import (
    I18nResourceRegistry,
    Locale,
    LocaleResolutionContext,
    TranslationCatalog,
    TranslationKey,
    get_translation_service,
    t,
)


def load_plugin_catalogues(*register_hooks: Callable[..., None]) -> None:
    """Load the catalogues the given ``register_i18n_resources`` hookimpls register into a fresh translation service.

    Mirrors what the lifespan does at startup, so views render catalogue
    wording instead of their fallback. Call ``reset_translation_service`` after
    the test so the next one starts from an empty service again.
    """
    reset_translation_service()
    registry = I18nResourceRegistry()
    for register in register_hooks:
        register(registry=registry)
    result = get_translation_service().initialize(resources=registry.list_specs(), strict=True)
    assert result.is_success, result.message


def reset_translation_service() -> None:
    """Drop the cached translation service and the cached ``t`` results."""
    get_translation_service.cache_clear()
    t.cache_clear()


def make_translation_key(namespace: str = "incident", message_key: str = "created") -> TranslationKey:
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
    requested_locale: Locale | None = None,
    user_locale: Locale | None = None,
    default_locale: Locale = Locale.EN_US,
    supported_locales: list | None = None,
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
