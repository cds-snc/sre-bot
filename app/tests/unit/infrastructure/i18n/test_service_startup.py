"""Tests for TranslationService startup and health checks."""

from pathlib import Path
from unittest.mock import Mock, patch

from infrastructure.i18n.models import Locale, TranslationKey
from infrastructure.i18n.resources import I18nResourceSpec
from infrastructure.i18n.service import TranslationService


class TestTranslationServiceInitialization:
    """Test TranslationService lifecycle and initialization."""

    def test_service_creation_is_side_effect_safe(self) -> None:
        """Test that service creation doesn't load files."""
        # This should not raise or perform any file I/O
        service = TranslationService()
        assert service is not None
        assert service._is_initialized is False

    def test_initialize_with_empty_resources(self) -> None:
        """Test initialization with no resources succeeds with nothing to load."""
        service = TranslationService()

        service._translator = Mock()
        service._translator.get_available_locales = Mock(return_value=[Locale.EN_US])

        result = service.initialize(resources=[], strict=True)
        assert result.is_success
        assert service._is_initialized is True

    def test_initialize_loads_all_locales(self, tmp_path: Path) -> None:
        """Test that initialize processes registered resource paths."""
        service = TranslationService()
        service._translator = Mock()
        service._translator.catalogs = {}
        service._translator.get_available_locales = Mock(return_value=[Locale.EN_US, Locale.FR_FR])

        core_dir = tmp_path / "core_locales"
        core_dir.mkdir()

        spec = I18nResourceSpec(owner="core", path=str(core_dir))
        # Existing directory has no YAML files — path is processed, ValueError skipped.
        result = service.initialize(resources=[spec], strict=True)

        assert result.is_success
        assert service._is_initialized is True

    def test_initialize_required_resource_missing(self) -> None:
        """Test initialization fails when required resource is missing."""
        service = TranslationService()

        spec = I18nResourceSpec(
            owner="pkg",
            path="/nonexistent/missing/path",
            required=True,
        )

        result = service.initialize(resources=[spec], strict=True)
        assert not result.is_success
        assert "missing" in result.message.lower()
        assert service._is_initialized is False

    def test_initialize_optional_resource_missing(self) -> None:
        """Test initialization continues when optional resource is missing."""
        service = TranslationService()
        service._translator = Mock()
        service._translator.load_all = Mock()
        service._translator.get_available_locales = Mock(return_value=[Locale.EN_US])

        spec = I18nResourceSpec(
            owner="pkg",
            path="/nonexistent/missing/path",
            required=False,
        )

        result = service.initialize(resources=[spec], strict=True)
        assert result.is_success
        assert service._is_initialized is True

    def test_initialize_translator_exception(self, tmp_path: Path) -> None:
        """Test initialization captures unexpected loader exceptions."""
        service = TranslationService()
        service._translator = Mock()
        service._translator.catalogs = {}

        core_dir = tmp_path / "core_locales"
        core_dir.mkdir()

        spec = I18nResourceSpec(owner="core", path=str(core_dir))
        with patch("infrastructure.i18n.service.YAMLTranslationLoader") as mock_loader_cls:
            mock_loader_cls.return_value.load_all.side_effect = RuntimeError("Parse error")
            result = service.initialize(resources=[spec], strict=True)

        assert not result.is_success
        assert "Parse error" in result.message
        assert service._is_initialized is False


class TestTranslationServiceHealthCheck:
    """Test TranslationService health checks."""

    def test_healthcheck_not_initialized(self) -> None:
        """Test health check fails when service not initialized."""
        service = TranslationService()
        result = service.health_check()

        assert not result.is_success
        assert "not initialized" in result.message.lower()

    def test_healthcheck_no_locales(self) -> None:
        """Test health check fails when no locales loaded."""
        service = TranslationService()
        service._translator = Mock()
        service._translator.get_available_locales = Mock(return_value=[])
        service._is_initialized = True

        result = service.health_check()

        assert not result.is_success
        assert "no available locales" in result.message.lower()

    def test_healthcheck_healthy(self) -> None:
        """Test health check passes when service initialized properly."""
        service = TranslationService()
        service._translator = Mock()
        service._translator.get_available_locales = Mock(return_value=[Locale.EN_US, Locale.FR_FR])
        service._is_initialized = True

        result = service.health_check()

        assert result.is_success

    def test_healthcheck_single_locale(self) -> None:
        """Test health check passes with single locale."""
        service = TranslationService()
        service._translator = Mock()
        service._translator.get_available_locales = Mock(return_value=[Locale.EN_US])
        service._is_initialized = True

        result = service.health_check()

        assert result.is_success


class TestTranslationServiceLifecycle:
    """Test complete TranslationService lifecycle."""

    def test_full_startup_flow(self, tmp_path: Path) -> None:
        """Test complete startup: create -> initialize -> healthcheck."""
        # Create service (side-effect safe)
        service = TranslationService()
        assert service._is_initialized is False

        # Mock translator for initialization
        service._translator = Mock()
        service._translator.load_all = Mock()
        service._translator.get_available_locales = Mock(return_value=[Locale.EN_US])

        # Initialize with resources
        core_dir = tmp_path / "core_locales"
        core_dir.mkdir()

        spec = I18nResourceSpec(owner="core", path=str(core_dir))
        init_result = service.initialize(resources=[spec], strict=True)
        assert init_result.is_success
        assert service._is_initialized is True

        # Health check
        health_result = service.health_check()
        assert health_result.is_success

    def test_translate_before_initialization_still_works(self) -> None:
        """Test that translate still delegates to translator even if not initialized."""
        service = TranslationService()
        service._translator = Mock()
        service._translator.translate_message = Mock(return_value="Hello")

        # translate() should still work even if _is_initialized is False
        # because it just delegates to the underlying translator

        result = service.translate(
            key=TranslationKey.from_string("test.key"),
            locale=Locale.EN_US,
        )
        assert result == "Hello"
