"""Tests for infrastructure.i18n.models module."""

import pytest

from infrastructure.i18n.models import (
    Locale,
    LocaleResolutionContext,
    TranslationCatalog,
    TranslationKey,
)
from tests.factories.i18n import (
    make_locale_resolution_context,
    make_translation_catalog,
    make_translation_key,
)


class TestLocale:
    """Tests for Locale enum."""

    def test_locale_enum_values(self):
        """Locale enum has expected values."""
        assert Locale.EN_US.value == "en-US"
        assert Locale.FR_FR.value == "fr-FR"

    def test_locale_from_string_valid(self):
        """from_string() accepts valid locale strings."""
        assert Locale.from_string("en-US") == Locale.EN_US
        assert Locale.from_string("fr-FR") == Locale.FR_FR

    def test_locale_from_string_invalid(self):
        """from_string() raises ValueError for invalid locales."""
        with pytest.raises(ValueError):
            Locale.from_string("xx-XX")

    def test_locale_language_property(self):
        """language property extracts language code."""
        assert Locale.EN_US.language == "en"
        assert Locale.FR_FR.language == "fr"

    def test_locale_region_property(self):
        """region property extracts region code."""
        assert Locale.EN_US.region == "US"
        assert Locale.FR_FR.region == "FR"


class TestTranslationKey:
    """Tests for TranslationKey model."""

    def test_translation_key_creation(self):
        """TranslationKey can be created with namespace and message_key."""
        key = TranslationKey(namespace="incident", message_key="created")
        assert key.namespace == "incident"
        assert key.message_key == "created"

    def test_translation_key_str_representation(self):
        """__str__() returns dot-separated path."""
        key = TranslationKey(namespace="incident", message_key="created")
        assert str(key) == "incident.created"

    def test_translation_key_from_string(self):
        """from_string() creates key from dot-separated string."""
        key = TranslationKey.from_string("incident.created")
        assert key.namespace == "incident"
        assert key.message_key == "created"

    def test_translation_key_from_string_invalid(self):
        """from_string() raises ValueError for invalid formats."""
        with pytest.raises(ValueError):
            TranslationKey.from_string("invalid")

        # "too.many.dots" is actually valid (becomes namespace="too", message_key="many.dots")
        key = TranslationKey.from_string("too.many.dots")
        assert key.namespace == "too"
        assert key.message_key == "many.dots"

    def test_translation_key_immutability(self):
        """TranslationKey is frozen (immutable)."""
        key = TranslationKey(namespace="incident", message_key="created")
        with pytest.raises(AttributeError):
            key.namespace = "role"

    def test_translation_key_hashable(self):
        """TranslationKey can be used as dict key."""
        key1 = TranslationKey(namespace="incident", message_key="created")
        key2 = TranslationKey(namespace="incident", message_key="created")
        key3 = TranslationKey(namespace="incident", message_key="resolved")

        d = {key1: "value1"}
        assert d[key2] == "value1"  # Same key
        assert key3 not in d


class TestTranslationCatalog:
    """Tests for TranslationCatalog model."""

    def test_catalog_creation(self):
        """TranslationCatalog can be created with locale."""
        catalog = TranslationCatalog(locale=Locale.EN_US)
        assert catalog.locale == Locale.EN_US
        assert catalog.messages == {}

    def test_catalog_with_messages(self):
        """TranslationCatalog can be initialized with messages."""
        messages = {
            "incident": {"created": "Incident created"},
        }
        catalog = TranslationCatalog(locale=Locale.EN_US, messages=messages)
        assert catalog.messages == messages

    def test_catalog_get_message(self):
        """get_message() retrieves message by key."""
        catalog = make_translation_catalog()
        key = make_translation_key(namespace="incident", message_key="created")
        assert catalog.get_message(key) == "Incident created"

    def test_catalog_get_message_not_found(self):
        """get_message() returns None for missing keys."""
        catalog = make_translation_catalog()
        key = make_translation_key(namespace="incident", message_key="nonexistent")
        assert catalog.get_message(key) is None

    def test_catalog_set_message(self):
        """set_message() adds or updates messages."""
        catalog = TranslationCatalog(locale=Locale.EN_US)
        key = make_translation_key(namespace="incident", message_key="created")
        catalog.set_message(key, "New incident created")

        assert catalog.get_message(key) == "New incident created"

    def test_catalog_has_message(self):
        """has_message() checks for message existence."""
        catalog = make_translation_catalog()
        key_exists = make_translation_key(namespace="incident", message_key="created")
        key_missing = make_translation_key(namespace="incident", message_key="missing")

        assert catalog.has_message(key_exists)
        assert not catalog.has_message(key_missing)

    def test_catalog_get_namespace(self):
        """get_namespace() returns all messages in namespace."""
        catalog = make_translation_catalog()
        incident_ns = catalog.get_namespace("incident")

        assert "created" in incident_ns
        assert "resolved" in incident_ns
        assert incident_ns["created"] == "Incident created"

    def test_catalog_get_namespace_empty(self):
        """get_namespace() returns empty dict for missing namespace."""
        catalog = make_translation_catalog()
        missing_ns = catalog.get_namespace("nonexistent")
        assert missing_ns == {}

    def test_catalog_merge(self):
        """merge() combines catalogs with later entries overriding earlier."""
        catalog1 = TranslationCatalog(
            locale=Locale.EN_US,
            messages={"incident": {"created": "Old message"}},
        )
        catalog2 = TranslationCatalog(
            locale=Locale.EN_US,
            messages={"incident": {"created": "New message", "resolved": "Resolved"}},
        )

        catalog1.merge(catalog2)

        assert (
            catalog1.get_message(make_translation_key("incident", "created"))
            == "New message"
        )
        assert (
            catalog1.get_message(make_translation_key("incident", "resolved"))
            == "Resolved"
        )


class TestLocaleResolutionContext:
    """Tests for LocaleResolutionContext model."""

    def test_context_creation(self):
        """LocaleResolutionContext can be created with default values."""
        context = LocaleResolutionContext()
        assert context.default_locale == Locale.EN_US
        assert context.requested_locale is None
        assert context.user_locale is None

    def test_context_with_preferences(self):
        """LocaleResolutionContext accepts locale preferences."""
        context = make_locale_resolution_context(
            requested_locale=Locale.FR_FR,
            user_locale=Locale.EN_US,
        )
        assert context.requested_locale == Locale.FR_FR
        assert context.user_locale == Locale.EN_US

    def test_context_resolve_requested_preferred(self):
        """resolve() prioritizes requested_locale."""
        context = make_locale_resolution_context(
            requested_locale=Locale.FR_FR,
            user_locale=Locale.EN_US,
        )
        assert context.resolve() == Locale.FR_FR

    def test_context_resolve_user_fallback(self):
        """resolve() uses user_locale if requested not set."""
        context = make_locale_resolution_context(
            requested_locale=None,
            user_locale=Locale.FR_FR,
        )
        assert context.resolve() == Locale.FR_FR

    def test_context_resolve_default_fallback(self):
        """resolve() uses default_locale as last resort."""
        context = make_locale_resolution_context(
            requested_locale=None,
            user_locale=None,
        )
        assert context.resolve() == Locale.EN_US

    def test_context_resolve_unsupported_requested(self):
        """resolve() skips unsupported requested_locale."""
        context = make_locale_resolution_context(
            requested_locale=Locale.FR_FR,
            user_locale=Locale.EN_US,
            supported_locales=[Locale.EN_US],
        )
        # FR_FR not supported, falls back to user_locale
        assert context.resolve() == Locale.EN_US

    def test_context_resolve_unsupported_user(self):
        """resolve() skips unsupported user_locale."""
        context = make_locale_resolution_context(
            requested_locale=None,
            user_locale=Locale.FR_FR,
            supported_locales=[Locale.EN_US],
        )
        # FR_FR not supported, falls back to default
        assert context.resolve() == Locale.EN_US
