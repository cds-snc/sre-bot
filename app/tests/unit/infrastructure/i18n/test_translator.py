"""Tests for infrastructure.i18n.translator module."""

# pylint: disable=protected-access

import pytest

from infrastructure.i18n import (
    Locale,
    Translator,
)
from infrastructure.i18n.models import TranslationKey


class TestTranslator:
    """Tests for Translator service."""

    @pytest.fixture
    def translator(self, yaml_loader):
        """Create Translator instance with test loader."""
        translator = Translator(yaml_loader, fallback_locale=Locale.EN_US)
        translator.load_all()
        return translator

    def test_translator_initialization(self, yaml_loader):
        """Translator initializes with loader and fallback locale."""
        translator = Translator(yaml_loader, fallback_locale=Locale.EN_US)
        assert translator.loader is yaml_loader
        assert translator.fallback_locale == Locale.EN_US
        assert len(translator.catalogs) == 0

    def test_load_all(self, translator):
        """load_all() loads all available locales."""
        assert len(translator.catalogs) == 2
        assert Locale.EN_US in translator.catalogs
        assert Locale.FR_FR in translator.catalogs

    def test_load_locale(self, translator):
        """load_locale() loads specific locale."""
        translator.catalogs.clear()
        translator.load_locale(Locale.EN_US)
        assert Locale.EN_US in translator.catalogs

    def test_translate_message_basic(self, translator):
        """translate_message() retrieves translated message."""
        key = TranslationKey("incident", "created")
        message = translator.translate_message(
            key,
            Locale.EN_US,
            variables={"incident_id": "INC-123"},
        )
        assert "Incident" in message
        assert "INC-123" in message

    def test_translate_message_with_variables(self, translator):
        """translate_message() interpolates variables."""
        key = TranslationKey("incident", "created")
        message = translator.translate_message(
            key,
            Locale.EN_US,
            variables={"incident_id": "INC-123"},
        )
        assert "INC-123" in message

    def test_translate_message_missing_variable_raises_error(self, translator):
        """translate_message() raises ValueError if variable not provided."""
        key = TranslationKey("incident", "created")
        # The "created" message has {{incident_id}} variable
        # Passing empty variables dict should raise ValueError
        with pytest.raises(ValueError):
            translator.translate_message(key, Locale.EN_US, variables={})

    def test_translate_message_french(self, translator):
        """translate_message() works with non-English locales."""
        key = TranslationKey("incident", "created")
        message = translator.translate_message(
            key,
            Locale.FR_FR,
            variables={"incident_id": "INC-456"},
        )
        assert "Incident" in message
        assert "créé" in message.lower()

    def test_translate_message_fallback_to_default(self, translator):
        """translate_message() falls back to default locale."""
        # Create a context where FR_FR doesn't have a message
        # Since test data has it, remove it temporarily
        del translator.catalogs[Locale.FR_FR].messages["incident"]["created"]

        key = TranslationKey("incident", "created")
        message = translator.translate_message(
            key,
            Locale.FR_FR,
            variables={"incident_id": "INC-789"},
        )
        # Should fall back to EN_US
        assert "Incident" in message

    def test_translate_message_key_not_found(self, translator):
        """translate_message() raises KeyError if key not found anywhere."""
        key = TranslationKey("nonexistent", "message")
        with pytest.raises(KeyError):
            translator.translate_message(key, Locale.EN_US)

    def test_has_message_exists(self, translator):
        """has_message() returns True for existing messages."""
        key = TranslationKey("incident", "created")
        assert translator.has_message(key, Locale.EN_US)

    def test_has_message_missing(self, translator):
        """has_message() returns False for missing messages."""
        key = TranslationKey("nonexistent", "message")
        assert not translator.has_message(key, Locale.EN_US)

    def test_has_message_wrong_locale(self, translator):
        """has_message() returns False for unloaded locales."""
        key = TranslationKey("incident", "created")
        # Remove FR_FR from catalogs
        translator.catalogs.pop(Locale.FR_FR, None)
        assert not translator.has_message(key, Locale.FR_FR)

    def test_get_available_locales(self, translator):
        """get_available_locales() returns loaded locales."""
        locales = translator.get_available_locales()
        assert Locale.EN_US in locales
        assert Locale.FR_FR in locales
        assert len(locales) == 2

    def test_get_catalog(self, translator):
        """get_catalog() returns complete catalog for locale."""
        catalog = translator.get_catalog(Locale.EN_US)
        assert catalog is not None
        assert "incident" in catalog.messages

    def test_get_catalog_unloaded(self, translator):
        """get_catalog() returns None for unloaded locale."""
        translator.catalogs.clear()
        catalog = translator.get_catalog(Locale.EN_US)
        assert catalog is None

    def test_reload(self, translator):
        """reload() resets and reloads all translations."""
        old_catalog = translator.catalogs[Locale.EN_US]
        translator.reload()
        new_catalog = translator.catalogs[Locale.EN_US]

        # Should be different object (reloaded)
        assert old_catalog is not new_catalog
        # But same content
        assert old_catalog.messages == new_catalog.messages


class TestTranslatorInterpolation:
    """Tests for variable interpolation in Translator."""

    @pytest.fixture
    def translator(self, yaml_loader):
        """Create Translator instance."""
        translator = Translator(yaml_loader)
        translator.load_all()
        return translator

    def test_interpolate_single_variable(self, translator):
        """_interpolate() replaces single variable."""
        message = "Incident {{incident_id}} created"
        result = translator._interpolate(message, {"incident_id": "INC-123"})
        assert result == "Incident INC-123 created"

    def test_interpolate_multiple_variables(self, translator):
        """_interpolate() replaces multiple variables."""
        message = "User {{user}} updated role {{role}}"
        result = translator._interpolate(
            message,
            {"user": "alice", "role": "admin"},
        )
        assert result == "User alice updated role admin"

    def test_interpolate_missing_variable(self, translator):
        """_interpolate() raises ValueError for missing variables."""
        message = "Incident {{incident_id}} created"
        with pytest.raises(ValueError):
            translator._interpolate(message, {"wrong_key": "value"})

    def test_interpolate_converts_to_string(self, translator):
        """_interpolate() converts numeric values to strings."""
        message = "Count: {{count}}"
        result = translator._interpolate(message, {"count": 42})
        assert result == "Count: 42"

    def test_interpolate_no_variables(self, translator):
        """_interpolate() returns unchanged message with no variables."""
        message = "Simple message"
        result = translator._interpolate(message, {})
        assert result == "Simple message"

    def test_interpolate_extra_variables_ignored(self, translator):
        """_interpolate() ignores extra variables in dict."""
        message = "Incident {{id}}"
        result = translator._interpolate(
            message,
            {"id": "123", "extra": "ignored"},
        )
        assert result == "Incident 123"
