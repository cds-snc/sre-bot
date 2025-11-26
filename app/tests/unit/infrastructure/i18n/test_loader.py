"""Tests for infrastructure.i18n.loader module."""

import pytest
import yaml

from infrastructure.i18n import Locale, YAMLTranslationLoader
from infrastructure.i18n.models import TranslationKey


class TestYAMLTranslationLoader:
    """Tests for YAMLTranslationLoader."""

    def test_loader_initialization(self, temp_translations_dir):
        """YAMLTranslationLoader initializes with valid directory."""
        loader = YAMLTranslationLoader(temp_translations_dir)
        assert loader.translations_dir == temp_translations_dir
        assert loader.use_cache is True
        assert loader.cache == {}

    def test_loader_initialization_nonexistent_directory(self, tmp_path):
        """YAMLTranslationLoader raises ValueError for missing directory."""
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(ValueError):
            YAMLTranslationLoader(nonexistent)

    def test_loader_with_cache_disabled(self, temp_translations_dir):
        """YAMLTranslationLoader can be created with cache disabled."""
        loader = YAMLTranslationLoader(temp_translations_dir, use_cache=False)
        assert loader.use_cache is False

    def test_load_single_locale(self, temp_translations_dir):
        """load() reads translations for a single locale."""
        loader = YAMLTranslationLoader(temp_translations_dir)
        catalog = loader.load(Locale.EN_US)

        assert catalog.locale == Locale.EN_US
        assert "incident" in catalog.messages
        assert "role" in catalog.messages

    def test_load_all_namespaces(self, temp_translations_dir):
        """load() loads all namespaces from YAML files."""
        loader = YAMLTranslationLoader(temp_translations_dir)
        catalog = loader.load(Locale.EN_US)

        # Check incident namespace
        assert (
            catalog.get_message(TranslationKey("incident", "created"))
            == "Incident {{incident_id}} created"
        )

        # Check role namespace
        assert (
            catalog.get_message(TranslationKey("role", "created"))
            == "Role {{role_name}} created"
        )

    def test_load_french_locale(self, temp_translations_dir):
        """load() loads French translations correctly."""
        loader = YAMLTranslationLoader(temp_translations_dir)
        catalog = loader.load(Locale.FR_FR)

        assert catalog.locale == Locale.FR_FR
        # Check that French messages are present
        message = catalog.get_message(TranslationKey("incident", "created"))
        assert "créé" in message

    def test_load_missing_locale_raises_error(self, tmp_path):
        """load() raises FileNotFoundError for unsupported locale."""
        # Create directory with only en-US files, then try to load fr-FR
        en_us_yml = tmp_path / "test.en-US.yml"
        with open(en_us_yml, "w") as f:
            yaml.dump({"test": {"msg": "test"}}, f)

        loader = YAMLTranslationLoader(tmp_path)

        # Try to load FR_FR which doesn't exist
        with pytest.raises(FileNotFoundError):
            loader.load(Locale.FR_FR)

    def test_load_caches_results(self, temp_translations_dir):
        """load() caches catalog when use_cache=True."""
        loader = YAMLTranslationLoader(temp_translations_dir, use_cache=True)
        catalog1 = loader.load(Locale.EN_US)
        catalog2 = loader.load(Locale.EN_US)

        # Should be same object (from cache)
        assert catalog1 is catalog2

    def test_load_no_cache_separate_instances(self, temp_translations_dir):
        """load() returns separate instances when use_cache=False."""
        loader = YAMLTranslationLoader(temp_translations_dir, use_cache=False)
        catalog1 = loader.load(Locale.EN_US)
        catalog2 = loader.load(Locale.EN_US)

        # Should be different objects
        assert catalog1 is not catalog2
        # But with same content
        assert catalog1.messages == catalog2.messages

    def test_load_all_locales(self, temp_translations_dir):
        """load_all() loads catalogs for all detected locales."""
        loader = YAMLTranslationLoader(temp_translations_dir)
        catalogs = loader.load_all()

        assert Locale.EN_US in catalogs
        assert Locale.FR_FR in catalogs
        assert len(catalogs) == 2

    def test_load_all_empty_directory(self, tmp_path):
        """load_all() raises ValueError for directory with no YAML files."""
        with pytest.raises(ValueError):
            loader = YAMLTranslationLoader(tmp_path, use_cache=False)
            loader.load_all()

    def test_load_all_populates_cache(self, temp_translations_dir):
        """load_all() populates cache when enabled."""
        loader = YAMLTranslationLoader(temp_translations_dir, use_cache=True)
        loader.load_all()

        assert len(loader.cache) == 2
        assert Locale.EN_US in loader.cache
        assert Locale.FR_FR in loader.cache

    def test_merge_yaml_data_multiple_files(self, temp_translations_dir):
        """Translations from multiple YAML files are merged correctly."""
        loader = YAMLTranslationLoader(temp_translations_dir)
        catalog = loader.load(Locale.EN_US)

        # Should have messages from both incident.en-US.yml and role.en-US.yml
        assert "incident" in catalog.messages
        assert "role" in catalog.messages
        assert len(catalog.messages["incident"]) > 0
        assert len(catalog.messages["role"]) > 0

    def test_clear_cache(self, temp_translations_dir):
        """clear_cache() removes cached catalogs."""
        loader = YAMLTranslationLoader(temp_translations_dir, use_cache=True)
        loader.load(Locale.EN_US)
        assert len(loader.cache) > 0

        loader.clear_cache()
        assert len(loader.cache) == 0

    def test_load_invalid_yaml_raises_error(self, tmp_path):
        """load() raises ValueError for invalid YAML."""
        # Create invalid YAML file
        invalid_yaml = tmp_path / "invalid.en-US.yml"
        with open(invalid_yaml, "w") as f:
            f.write("invalid: yaml: content: [")

        loader = YAMLTranslationLoader(tmp_path)
        with pytest.raises(ValueError):
            loader.load(Locale.EN_US)

    def test_load_non_dict_yaml_skipped(self, tmp_path):
        """load() skips YAML content that isn't a dict."""
        # Create YAML file with list instead of dict
        invalid_yaml = tmp_path / "invalid.en-US.yml"
        with open(invalid_yaml, "w") as f:
            yaml.dump(["item1", "item2"], f)

        loader = YAMLTranslationLoader(tmp_path)
        # Should not raise, but catalog will be empty
        catalog = loader.load(Locale.EN_US)
        assert catalog.messages == {}
