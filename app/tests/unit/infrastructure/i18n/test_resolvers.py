"""Tests for infrastructure.i18n.resolvers module."""

import pytest

from infrastructure.i18n import Locale, LocaleResolver, LanguageNegotiator


class TestLocaleResolver:
    """Tests for LocaleResolver service."""

    def test_resolver_initialization(self):
        """LocaleResolver initializes with default locale."""
        resolver = LocaleResolver(default_locale=Locale.EN_US)
        assert resolver.default_locale == Locale.EN_US

    def test_resolve_from_header_simple(self):
        """resolve_from_header() handles simple language tag."""
        resolver = LocaleResolver()
        result = resolver.resolve_from_header("en")
        assert result == Locale.EN_US

    def test_resolve_from_header_specific(self):
        """resolve_from_header() matches specific locale."""
        resolver = LocaleResolver()
        result = resolver.resolve_from_header("en-US")
        assert result == Locale.EN_US

    def test_resolve_from_header_french(self):
        """resolve_from_header() resolves French."""
        resolver = LocaleResolver()
        result = resolver.resolve_from_header("fr-FR")
        assert result == Locale.FR_FR

    def test_resolve_from_header_language_only_match(self):
        """resolve_from_header() matches language without region."""
        resolver = LocaleResolver()
        # Request "en" should match "en-US"
        result = resolver.resolve_from_header("en")
        assert result == Locale.EN_US

    def test_resolve_from_header_with_quality(self):
        """resolve_from_header() respects quality preferences."""
        resolver = LocaleResolver()
        # en-US has priority 1.0, fr-FR has 0.8
        result = resolver.resolve_from_header("en-US,en;q=0.9,fr-FR;q=0.8")
        assert result == Locale.EN_US

    def test_resolve_from_header_quality_ordering(self):
        """resolve_from_header() uses quality for ordering."""
        resolver = LocaleResolver()
        # fr-FR has priority 0.9, en-US has 0.8
        result = resolver.resolve_from_header("fr-FR;q=0.9,en-US;q=0.8")
        assert result == Locale.FR_FR

    def test_resolve_from_header_no_match_default(self):
        """resolve_from_header() returns default if no match."""
        resolver = LocaleResolver(default_locale=Locale.EN_US)
        result = resolver.resolve_from_header("de-DE")
        assert result == Locale.EN_US

    def test_resolve_from_header_empty_string(self):
        """resolve_from_header() handles empty string."""
        resolver = LocaleResolver()
        result = resolver.resolve_from_header("")
        assert result == Locale.EN_US

    def test_resolve_from_header_none(self):
        """resolve_from_header() handles None."""
        resolver = LocaleResolver()
        result = resolver.resolve_from_header(None)
        assert result == Locale.EN_US

    def test_resolve_from_header_custom_supported(self):
        """resolve_from_header() filters by supported locales."""
        resolver = LocaleResolver()
        supported = [Locale.FR_FR]  # Only French supported
        result = resolver.resolve_from_header(
            "en-US,fr-FR", supported_locales=supported
        )
        assert result == Locale.FR_FR

    def test_resolve_from_string_valid(self):
        """resolve_from_string() parses valid locale string."""
        resolver = LocaleResolver()
        result = resolver.resolve_from_string("en-US")
        assert result == Locale.EN_US

    def test_resolve_from_string_invalid(self):
        """resolve_from_string() raises ValueError for invalid locale."""
        resolver = LocaleResolver()
        with pytest.raises(ValueError):
            resolver.resolve_from_string("xx-XX")


class TestLanguageNegotiator:
    """Tests for LanguageNegotiator service."""

    def test_matches_language_exact(self):
        """matches_language() returns True for exact match."""
        assert LanguageNegotiator.matches_language("en-US", "en-US")
        assert LanguageNegotiator.matches_language("en-US", "en-US", strict=True)

    def test_matches_language_language_only(self):
        """matches_language() matches language without region when not strict."""
        assert LanguageNegotiator.matches_language("en-US", "en", strict=False)
        assert LanguageNegotiator.matches_language("en", "en-US", strict=False)

    def test_matches_language_case_insensitive(self):
        """matches_language() is case-insensitive."""
        assert LanguageNegotiator.matches_language("EN-US", "en-US")
        assert LanguageNegotiator.matches_language("en-us", "EN-US")

    def test_matches_language_strict_no_match(self):
        """matches_language() returns False for different regions in strict mode."""
        assert not LanguageNegotiator.matches_language("en-US", "en-GB", strict=True)

    def test_matches_language_strict_language_only(self):
        """matches_language() returns False when matching language-only in strict mode."""
        assert not LanguageNegotiator.matches_language("en-US", "en", strict=True)

    def test_find_best_match_exact(self):
        """find_best_match() returns exact match."""
        requested = ["en-US"]
        available = ["en-US", "fr-FR"]
        result = LanguageNegotiator.find_best_match(requested, available)
        assert result == "en-US"

    def test_find_best_match_language_only(self):
        """find_best_match() falls back to language-only match."""
        requested = ["en-US"]
        available = ["en", "fr"]
        result = LanguageNegotiator.find_best_match(requested, available)
        assert result == "en"

    def test_find_best_match_preference_order(self):
        """find_best_match() respects preference order."""
        requested = ["fr-FR", "en-US"]
        available = ["en-US", "fr-FR"]
        result = LanguageNegotiator.find_best_match(requested, available)
        assert result == "fr-FR"

    def test_find_best_match_no_match(self):
        """find_best_match() returns None if no match."""
        requested = ["de-DE"]
        available = ["en-US", "fr-FR"]
        result = LanguageNegotiator.find_best_match(requested, available)
        assert result is None

    def test_find_best_match_default(self):
        """find_best_match() returns default if no match."""
        requested = ["de-DE"]
        available = ["en-US", "fr-FR"]
        result = LanguageNegotiator.find_best_match(
            requested, available, default="en-US"
        )
        assert result == "en-US"

    def test_find_best_match_empty_requested(self):
        """find_best_match() handles empty requested list."""
        requested = []
        available = ["en-US"]
        result = LanguageNegotiator.find_best_match(requested, available)
        assert result is None
