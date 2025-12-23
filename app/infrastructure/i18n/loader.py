"""Translation loading interface and implementations.

Defines the contract for loading translations and provides YAML-based loader.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict

import yaml

import structlog
from infrastructure.i18n.models import Locale, TranslationCatalog

logger = structlog.get_logger()


class TranslationLoader(ABC):
    """Abstract base for translation loaders.

    Implementations must define how to load and parse translation files
    for different locales.
    """

    @abstractmethod
    def load(self, locale: Locale) -> TranslationCatalog:
        """Load translations for a specific locale.

        Args:
            locale: Locale to load translations for.

        Returns:
            TranslationCatalog with loaded messages.

        Raises:
            FileNotFoundError: If translation files not found.
            ValueError: If translation format is invalid.
        """
        pass

    @abstractmethod
    def load_all(self) -> Dict[Locale, TranslationCatalog]:
        """Load translations for all supported locales.

        Returns:
            Dict mapping Locale to TranslationCatalog.
        """
        pass


class YAMLTranslationLoader(TranslationLoader):
    """Loader for YAML-based translation files.

    Expects files in format: <locale>.yml or <domain>.<locale>.yml
    in the specified translations directory.

    Attributes:
        translations_dir: Path to directory containing YAML files.
        cache: Optional cache of loaded catalogs (locale -> catalog).
    """

    def __init__(
        self,
        translations_dir: Path,
        use_cache: bool = True,
    ):
        """Initialize YAML translation loader.

        Args:
            translations_dir: Path to directory with YAML translation files.
            use_cache: Whether to cache loaded catalogs in memory.
        """
        self.translations_dir = Path(translations_dir)
        self.use_cache = use_cache
        self.cache: Dict[Locale, TranslationCatalog] = {}

        if not self.translations_dir.exists():
            raise ValueError(
                f"Translations directory not found: {self.translations_dir}"
            )

        logger.info(
            "initialized_yaml_loader",
            translations_dir=str(self.translations_dir),
            use_cache=use_cache,
        )

    def load(self, locale: Locale) -> TranslationCatalog:
        """Load translations for a locale from YAML files.

        Searches for files matching pattern: *.<locale>.yml
        Merges all matching files into single catalog.

        Args:
            locale: Locale to load.

        Returns:
            TranslationCatalog with loaded messages.

        Raises:
            FileNotFoundError: If no YAML files found for locale.
            ValueError: If YAML parsing fails.
        """
        if self.use_cache and locale in self.cache:
            logger.info("loaded_from_cache", locale=locale.value)
            return self.cache[locale]

        catalog = TranslationCatalog(locale=locale)
        yaml_files = sorted(self.translations_dir.glob(f"*.{locale.value}.yml"))

        if not yaml_files:
            raise FileNotFoundError(
                f"No translation files found for locale {locale.value} in {self.translations_dir}"
            )

        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data:
                        self._merge_yaml_data(catalog, data, yaml_file)
            except yaml.YAMLError as e:
                logger.error("yaml_parse_error", file=str(yaml_file), error=str(e))
                raise ValueError(f"Failed to parse {yaml_file}: {e}") from e

        logger.info(
            "loaded_translations",
            locale=locale.value,
            file_count=len(yaml_files),
            namespace_count=len(catalog.messages),
        )

        if self.use_cache:
            self.cache[locale] = catalog

        return catalog

    def load_all(self) -> Dict[Locale, TranslationCatalog]:
        """Load translations for all supported locales.

        Detects available locales from .yml files and loads each.

        Returns:
            Dict mapping each Locale to its TranslationCatalog.

        Raises:
            ValueError: If no translation files found at all.
        """
        locales_found = set()
        for yaml_file in self.translations_dir.glob("*.yml"):
            # Extract locale from filename (e.g., "incident.en-US.yml" -> "en-US")
            parts = yaml_file.stem.split(".")
            if len(parts) >= 2:
                locale_str = parts[-1]
                try:
                    locale = Locale.from_string(locale_str)
                    locales_found.add(locale)
                except ValueError:
                    # Skip files with unrecognized locale format
                    pass

        if not locales_found:
            raise ValueError(f"No translation files found in {self.translations_dir}")

        result = {}
        for locale in locales_found:
            try:
                result[locale] = self.load(locale)
            except FileNotFoundError:
                logger.warning("could_not_load_locale", locale=locale.value)

        return result

    def _merge_yaml_data(
        self,
        catalog: TranslationCatalog,
        data: Dict,
        source_file: Path,
    ) -> None:
        """Merge YAML data into catalog.

        Expected format:
        namespace:
          key1: message1
          key2: message2

        Args:
            catalog: TranslationCatalog to merge into.
            data: Parsed YAML data.
            source_file: Source file (for logging).
        """
        if not isinstance(data, dict):
            logger.warning(
                "invalid_yaml_format", file=str(source_file), expected="dict"
            )
            return

        for namespace, messages in data.items():
            if not isinstance(messages, dict):
                logger.warning(
                    "invalid_namespace_format",
                    namespace=namespace,
                    expected="dict",
                )
                continue

            if namespace not in catalog.messages:
                catalog.messages[namespace] = {}

            catalog.messages[namespace].update(messages)

    def clear_cache(self) -> None:
        """Clear all cached translations."""
        self.cache.clear()
        logger.info("cleared_translation_cache")
