"""Translation service for dependency injection.

Provides a class-based interface to the i18n system for easier DI and testing.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from infrastructure.i18n.loader import YAMLTranslationLoader
from infrastructure.i18n.models import Locale, TranslationKey
from infrastructure.i18n.translator import Translator
from infrastructure.operations import OperationResult, OperationStatus

import structlog


class TranslationService:
    """Class-based translation service.

    Wraps the Translator instance with a service interface to support
    dependency injection and easier testing with mocks.

    This is a thin facade - all actual work is delegated to the underlying
    Translator instance created by the factory.

    Lifecycle:
      1. Create via __init__ - side-effect safe, no file I/O
      2. Initialize via initialize() during startup - loads translation files
      3. Health check via health_check() - validates loaded catalogs

    Usage:
        # Via dependency injection (routes)
        from infrastructure.i18n import TranslationServiceDep

        @router.get("/message")
        def get_message(translation: TranslationServiceDep):
            msg = translation.translate(
                key=TranslationKey.from_string("common.welcome"),
                locale=Locale.EN_US
            )
            return {"message": msg}

        # Initialization (lifespan)
        from infrastructure.i18n import get_translation_service, I18nResourceSpec

        translation = get_translation_service()
        resources = [
            I18nResourceSpec(owner="core", path="app/locales", required=True)
        ]
        result = translation.initialize(resources=resources)
        if result.is_failure:
            raise RuntimeError(f"i18n initialization failed: {result.error}")
    """

    def __init__(self, translator: Optional[Translator] = None):
        """Initialize translation service side-effect safe.

        Args:
            translator: Pre-configured Translator instance.
        """
        self._translator = translator
        self._is_initialized = False

    def initialize(
        self, resources: List[Any], strict: bool = True
    ) -> OperationResult[None]:
        """Initialize translation service with registered resources.

        Must be called during startup before translating messages.

        Args:
            resources: List of I18nResourceSpec from registry.
            strict: If True, fail on any catalog parse error. If False, warn only.

        Returns:
            OperationResult.success() if initialization succeeded.
            OperationResult.error() if any required resource failed to load.
        """
        logger = structlog.get_logger()
        log = logger.bind(
            resource_count=len(resources), strict=strict, phase="i18n_init"
        )
        log.info("i18n_initialization_started")

        paths_to_load: List[Path] = []
        for resource in resources:
            # Extract path from I18nResourceSpec
            if hasattr(resource, "path"):
                path = Path(resource.path)
                if path.exists():
                    paths_to_load.append(path)
                elif hasattr(resource, "required") and resource.required:
                    error_msg = f"Required i18n resource not found: {path}"
                    log_bind = logger.bind(path=str(path), required=True)
                    log_bind.error("i18n_resource_missing")
                    return OperationResult.error(
                        status=OperationStatus.PERMANENT_ERROR,
                        message=error_msg,
                    )
                else:
                    log_bind = logger.bind(path=str(path), required=False)
                    log_bind.warning("i18n_optional_resource_missing")

        # Load translations from every registered path and merge into the translator.
        # Each path gets its own loader; results are merged so feature-package locales
        # (e.g. packages/geolocate/locales) are combined with core app/locales catalogs.
        try:
            for path in paths_to_load:
                try:
                    path_loader = YAMLTranslationLoader(
                        translations_dir=path, use_cache=False
                    )
                    new_catalogs = path_loader.load_all()
                    for locale, catalog in new_catalogs.items():
                        if locale in self._translator.catalogs:
                            # Merge namespaces into the existing catalog
                            for namespace, messages in catalog.messages.items():
                                self._translator.catalogs[locale].messages.setdefault(
                                    namespace, {}
                                ).update(messages)
                        else:
                            self._translator.catalogs[locale] = catalog
                except (FileNotFoundError, ValueError) as path_error:
                    logger.bind(path=str(path), error=str(path_error)).warning(
                        "i18n_path_load_skipped"
                    )

            self._is_initialized = True

            log = logger.bind(
                paths_loaded=len(paths_to_load),
                locales_available=len(self._translator.get_available_locales()),
            )
            log.info("i18n_initialization_completed")
            return OperationResult.success()

        except Exception as exc:
            error_msg = f"i18n initialization failed: {str(exc)}"
            log = logger.bind(error=error_msg)
            log.error("i18n_initialization_failed")
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message=error_msg,
            )

    def health_check(self) -> OperationResult[None]:
        """Validate translation service health.

        Checks that service is initialized and catalogs are loaded.

        Returns:
            OperationResult.success() if service is healthy.
            OperationResult.error() if initialization incomplete or catalogs missing.
        """
        logger = structlog.get_logger()

        if not self._is_initialized:
            error_msg = "i18n service not initialized"
            logger.error("i18n_healthcheck_failed", reason="not_initialized")
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message=error_msg,
            )

        available = self._translator.get_available_locales()
        if not available:
            error_msg = "i18n service has no available locales"
            logger.error("i18n_healthcheck_failed", reason="no_locales")
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message=error_msg,
            )

        logger.info("i18n_healthcheck_passed", locale_count=len(available))
        return OperationResult.success()

    def translate(
        self,
        key: TranslationKey,
        locale: Locale,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Retrieve and interpolate a translated message.

        Args:
            key: TranslationKey identifying the message
            locale: Locale to translate to
            variables: Optional dict of variables for interpolation

        Returns:
            Translated and interpolated message string

        Raises:
            KeyError: If key not found in requested locale or fallback locale
        """
        return self._translator.translate_message(key, locale, variables)

    def has_message(self, key: TranslationKey, locale: Locale) -> bool:
        """Check if translation exists for key in locale.

        Args:
            key: TranslationKey to check
            locale: Locale to check

        Returns:
            True if message exists in requested locale, False otherwise
        """
        return self._translator.has_message(key, locale)

    def get_available_locales(self) -> list[Locale]:
        """Get list of loaded locales.

        Returns:
            List of Locale enums that have been loaded
        """
        return self._translator.get_available_locales()

    def load_locale(self, locale: Locale) -> None:
        """Load specific locale from loader.

        Args:
            locale: Locale to load

        Raises:
            FileNotFoundError: If translation files not found
        """
        self._translator.load_locale(locale)

    def load_all(self) -> None:
        """Load all available locales from loader."""
        self._translator.load_all()

    @property
    def translator(self) -> Translator:
        """Access underlying Translator instance.

        Provided for advanced use cases that need direct access
        to the Translator API.

        Returns:
            The underlying Translator instance
        """
        return self._translator
