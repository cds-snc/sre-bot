"""Tests for Settings aggregator deprecation behavior (ADR-0055)."""

import pytest

from infrastructure.configuration.settings import Settings
from infrastructure.services.providers import get_settings


class TestSettingsDeprecation:
    """Validate deprecation warning while preserving compatibility."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self):
        """Ensure each test gets a fresh Settings construction path."""
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    def test_settings_emits_deprecation_warning(self):
        """Constructing Settings emits DeprecationWarning."""
        with pytest.warns(DeprecationWarning):
            Settings()

    def test_get_settings_still_works(self):
        """get_settings remains backward compatible while deprecated."""
        with pytest.warns(DeprecationWarning):
            settings = get_settings()

        assert isinstance(settings, Settings)

    def test_deprecation_message_references_adr(self):
        """Warning message references ADR guidance."""
        with pytest.warns(DeprecationWarning, match="ADR-0055"):
            Settings()
