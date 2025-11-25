"""Integration tests for command provider system."""

from unittest.mock import MagicMock, patch

import pytest
from infrastructure.commands import CommandRegistry
from infrastructure.commands.providers import (
    _discovered,
    get_active_providers,
    get_provider,
    load_providers,
    register_command_provider,
    reset_registry,
)
from infrastructure.commands.providers.base import CommandProvider


class MockCommandProvider(CommandProvider):
    """Mock adapter for integration testing."""

    def __init__(self, config):
        super().__init__(registry=None)
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


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up registry before and after each test."""
    reset_registry()
    _discovered.clear()
    yield
    reset_registry()
    _discovered.clear()


class TestCommandProviderIntegration:
    """Integration tests for command provider activation."""

    def test_full_provider_lifecycle(self):
        """Test full lifecycle: register → load → get → use."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"test": {"enabled": True}}

        with patch("infrastructure.commands.providers.settings", mock_settings):
            # Load providers (discover + activate)
            providers = load_providers()

            assert len(providers) == 1
            assert "test" in providers

            # Get provider
            provider = get_provider("test")
            assert isinstance(provider, TestAdapter)

            # Use provider
            assert provider.config == {"enabled": True}

    def test_load_providers_with_multiple_providers(self):
        """Test loading multiple registered providers."""

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

        with patch("infrastructure.commands.providers.settings", mock_settings):
            # Load providers
            providers = load_providers()

            assert len(providers) == 2
            assert get_provider("test1")
            assert get_provider("test2")

    def test_load_providers_mixed_enabled_disabled(self):
        """Test loading with mix of enabled/disabled providers."""

        @register_command_provider("enabled")
        class EnabledAdapter(MockCommandProvider):
            pass

        @register_command_provider("disabled")
        class DisabledAdapter(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {
            "enabled": {"enabled": True},
            "disabled": {"enabled": False},
        }

        with patch("infrastructure.commands.providers.settings", mock_settings):
            # Load providers
            providers = load_providers()

            # Only enabled provider should be active
            assert len(providers) == 1
            assert "enabled" in providers
            assert "disabled" not in providers

    def test_load_providers_api_only_mode(self):
        """Test load_providers in API-only mode."""
        # Mock settings with no providers
        mock_settings = MagicMock()
        mock_settings.commands.providers = {}

        with patch("infrastructure.commands.providers.settings", mock_settings):
            # Load providers
            providers = load_providers()

            assert providers == {}
            assert len(get_active_providers()) == 0

    def test_provider_config_passed_correctly(self):
        """Test that provider config is passed during instantiation."""

        captured_config = {}

        @register_command_provider("test")
        class ConfigCapturingAdapter(MockCommandProvider):
            def __init__(self, config):
                captured_config.update(config)
                super().__init__(config)

        test_config = {"enabled": True, "custom_field": "custom_value"}

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"test": test_config}

        with patch("infrastructure.commands.providers.settings", mock_settings):
            # Load providers
            load_providers()

            # Verify config was passed correctly
            assert captured_config == test_config

    def test_provider_error_handling(self):
        """Test that provider instantiation errors are handled."""

        @register_command_provider("failing")
        class FailingAdapter(MockCommandProvider):
            def __init__(self, config):
                raise RuntimeError("Provider initialization failed")

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"failing": {"enabled": True}}

        with patch("infrastructure.commands.providers.settings", mock_settings):
            # Load providers should raise
            with pytest.raises(RuntimeError, match="Provider initialization failed"):
                load_providers()

    def test_concurrent_provider_access(self):
        """Test accessing providers from different parts of code."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"test": {"enabled": True}}

        with patch("infrastructure.commands.providers.settings", mock_settings):
            # Load providers
            load_providers()

            # Access from multiple "locations"
            prov1 = get_provider("test")
            prov2 = get_provider("test")

            # Should be same instance
            assert prov1 is prov2

    def test_provider_activation_idempotent(self):
        """Test that loading providers multiple times is safe."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"test": {"enabled": True}}

        with patch("infrastructure.commands.providers.settings", mock_settings):
            # Load once
            load_providers()
            prov1 = get_provider("test")

            # Reset and load again
            reset_registry()

            load_providers()
            prov2 = get_provider("test")

            # Both should work
            assert isinstance(prov1, TestAdapter)
            assert isinstance(prov2, TestAdapter)


class TestModuleIntegration:
    """Tests for module integration with provider system."""

    def test_module_attaches_registry_to_provider(self):
        """Test module can attach its registry to provider."""

        @register_command_provider("test")
        class TestAdapter(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"test": {"enabled": True}}

        with patch("infrastructure.commands.providers.settings", mock_settings):
            # Load providers
            load_providers()

            # Module gets provider and attaches registry
            provider = get_provider("test")
            test_registry = CommandRegistry("test")
            provider.registry = test_registry

            assert provider.registry == test_registry

    def test_different_modules_can_use_same_provider(self):
        """Test multiple modules can use same provider (with different registries)."""

        @register_command_provider("slack")
        class SlackAdapter(MockCommandProvider):
            pass

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.commands.providers = {"slack": {"enabled": True}}

        with patch("infrastructure.commands.providers.settings", mock_settings):
            # Load providers
            load_providers()

            # Module 1 gets provider
            provider1 = get_provider("slack")
            registry1 = CommandRegistry("groups")
            provider1.registry = registry1

            # Module 2 gets same provider
            provider2 = get_provider("slack")
            registry2 = CommandRegistry("incident")
            provider2.registry = registry2

            # Same provider instance, but last registry wins
            assert provider1 is provider2
            assert provider2.registry == registry2
