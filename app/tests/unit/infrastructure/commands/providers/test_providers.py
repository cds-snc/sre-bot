"""Unit tests for command provider system."""

from unittest.mock import MagicMock

import pytest
from infrastructure.commands.providers import (
    _discovered,
    activate_providers,
    get_active_providers,
    get_provider,
    register_command_provider,
    reset_registry,
)
from infrastructure.commands.providers.base import CommandProvider


class MockCommandProvider(CommandProvider):
    """Mock adapter for testing."""

    def __init__(self, settings, config):
        super().__init__(registry=None)
        self.settings = settings
        self.config = config

    def extract_command_text(self, payload):
        return payload.get("text", "")

    def create_context(self, payload):
        pass

    def acknowledge(self, payload):
        pass

    def send_error(self, payload, message):
        pass

    def send_help(self, payload, help_text):
        pass

    def _validate_payload(self, payload):
        pass

    def preprocess_command_text(self, payload, text):
        return text

    def _resolve_framework_locale(self, payload):
        return "en-US"


@pytest.fixture(autouse=True)
def cleanup_registry():
    """Reset registry before and after each test."""
    reset_registry()
    _discovered.clear()
    yield
    reset_registry()
    _discovered.clear()


class TestCommandProviderRegistration:
    """Tests for provider registration."""

    def test_register_provider_success(self):
        """Test successful provider registration."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        assert "test" in _discovered
        assert _discovered["test"] == TestAdapter

    def test_register_provider_not_a_class(self):
        """Test registration fails if not a class."""

        with pytest.raises(TypeError, match="must be applied to a class"):

            @register_command_provider("test")
            def not_a_class():
                pass

    def test_register_provider_not_subclass_of_adapter(self):
        """Test registration fails if not CommandProvider subclass."""

        with pytest.raises(TypeError, match="must subclass CommandProvider"):

            @register_command_provider("test")
            class NotAdapter:
                pass

    def test_register_provider_duplicate_name(self):
        """Test registration fails on duplicate provider name."""

        @register_command_provider("test")
        class TestAdapter1(MockCommandProvider):
            pass

        with pytest.raises(RuntimeError, match="already registered"):

            @register_command_provider("test")
            class TestAdapter2(MockCommandProvider):
                pass


class TestCommandProviderActivation:
    """Tests for provider activation."""

    def test_activate_no_providers(self):
        """Test activation with no providers configured."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        # Mock settings with no providers
        mock_settings = MagicMock()
        mock_settings.commands.providers = {}

        result = activate_providers(mock_settings)
        assert result == {}

    def test_activate_single_provider(self):
        """Test activation with single enabled provider."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"test": {"enabled": True}}

        result = activate_providers(mock_settings)
        assert len(result) == 1
        assert "test" in result
        assert isinstance(result["test"], TestAdapter)

    def test_activate_disabled_provider_ignored(self):
        """Test that disabled providers are not activated."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        # Mock settings with disabled provider
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"test": {"enabled": False}}

        result = activate_providers(mock_settings)
        assert result == {}

    def test_activate_provider_not_discovered(self):
        """Test that undiscovered providers are not activated."""
        # Mock settings with unknown provider
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"unknown": {"enabled": True}}

        result = activate_providers(mock_settings)
        assert result == {}

    def test_activate_provider_instantiation_error(self):
        """Test that activation error is raised and logged."""

        @register_command_provider("test")
        class FailingAdapter(MockCommandProvider):
            def __init__(self, settings, config):
                raise ValueError("Initialization failed")

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"test": {"enabled": True}}

        with pytest.raises(ValueError, match="Initialization failed"):
            activate_providers(mock_settings)

    def test_activate_multiple_providers(self):
        """Test activation with multiple providers."""

        @register_command_provider("test1")
        class TestAdapter1(MockCommandProvider):
            pass

        @register_command_provider("test2")
        class TestAdapter2(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {
            "test1": {"enabled": True},
            "test2": {"enabled": True},
        }

        result = activate_providers(mock_settings)
        assert len(result) == 2
        assert "test1" in result
        assert "test2" in result

    def test_activate_settings_attribute_error(self):
        """Test activation handles missing settings gracefully."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        # Mock settings without commands attribute
        mock_settings = MagicMock()
        del mock_settings.commands

        result = activate_providers(mock_settings)
        assert result == {}


class TestGetProvider:
    """Tests for get_provider function."""

    def test_get_provider_success(self):
        """Test getting active provider by name."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        # Mock settings and activate
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"test": {"enabled": True}}

        activate_providers(mock_settings)
        provider = get_provider("test")

        assert isinstance(provider, TestAdapter)

    def test_get_provider_not_active(self):
        """Test getting non-active provider raises error."""
        with pytest.raises(ValueError, match="not active"):
            get_provider("nonexistent")

    def test_get_provider_different_names(self):
        """Test getting different providers."""

        @register_command_provider("test1")
        class TestAdapter1(MockCommandProvider):
            pass

        @register_command_provider("test2")
        class TestAdapter2(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {
            "test1": {"enabled": True},
            "test2": {"enabled": True},
        }

        activate_providers(mock_settings)

        prov1 = get_provider("test1")
        prov2 = get_provider("test2")

        assert isinstance(prov1, TestAdapter1)
        assert isinstance(prov2, TestAdapter2)
        assert prov1 is not prov2


class TestGetActiveProviders:
    """Tests for get_active_providers function."""

    def test_get_active_providers_empty(self):
        """Test getting active providers when none active."""
        result = get_active_providers()
        assert result == {}

    def test_get_active_providers_returns_copy(self):
        """Test that returned dict is a copy."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"test": {"enabled": True}}

        activate_providers(mock_settings)
        result = get_active_providers()

        # Modify returned dict
        result["fake"] = MagicMock()

        # Original should not be modified
        assert "fake" not in get_active_providers()

    def test_get_active_providers_multiple(self):
        """Test getting multiple active providers."""

        @register_command_provider("test1")
        class TestAdapter1(MockCommandProvider):
            pass

        @register_command_provider("test2")
        class TestAdapter2(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {
            "test1": {"enabled": True},
            "test2": {"enabled": True},
        }

        activate_providers(mock_settings)
        result = get_active_providers()

        assert len(result) == 2
        assert "test1" in result
        assert "test2" in result


class TestResetRegistry:
    """Tests for reset_registry function."""

    def test_reset_registry_clears_active(self):
        """Test reset clears active providers."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"test": {"enabled": True}}

        activate_providers(mock_settings)
        assert len(get_active_providers()) == 1

        reset_registry()
        assert len(get_active_providers()) == 0


class TestAPIOnyMode:
    """Tests for API-only mode (no command providers)."""

    def test_api_only_mode_no_config(self):
        """Test API-only mode when COMMAND_PROVIDERS not configured."""
        # Mock settings without COMMAND_PROVIDERS
        mock_settings = MagicMock()
        mock_settings.commands = MagicMock()
        del mock_settings.commands.providers

        result = activate_providers(mock_settings)
        assert result == {}

    def test_api_only_mode_empty_config(self):
        """Test API-only mode with empty COMMAND_PROVIDERS."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {}

        result = activate_providers(mock_settings)
        assert result == {}

    def test_api_only_mode_get_provider_fails(self):
        """Test getting provider in API-only mode raises error."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {}

        activate_providers(mock_settings)

        with pytest.raises(ValueError, match="not active"):
            get_provider("slack")
