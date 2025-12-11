"""Tests for feature-level provider registry with primary/secondary separation.

Tests cover:
- Provider registration (primary, secondary, auto-detect)
- Single-stage activation with config passing
- Primary/secondary role separation and validation
- Registry accessor functions
- Error handling and edge cases
"""

# pylint: disable=protected-access,unused-argument

import pytest


class TestProviderRegistration:
    """Tests for provider discovery and registration decorators."""

    def test_register_primary_provider_success(self, monkeypatch, mock_primary_class):
        """Primary provider can be registered with decorator."""
        # Import fresh providers module
        import modules.groups.providers as providers

        # Reset registries for clean test
        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()

        # Register primary provider
        decorator = providers.register_primary_provider("test_primary")
        result = decorator(mock_primary_class)

        # Verify registration
        assert "test_primary" in providers._primary_discovered
        assert providers._primary_discovered["test_primary"] is mock_primary_class
        assert result is mock_primary_class

    def test_register_primary_provider_rejects_non_primary(
        self, monkeypatch, mock_secondary_class
    ):
        """Primary registration rejects non-PrimaryGroupProvider classes."""
        import modules.groups.providers as providers

        providers._primary_discovered.clear()

        decorator = providers.register_primary_provider("bad_primary")

        with pytest.raises(TypeError, match="must subclass PrimaryGroupProvider"):
            decorator(mock_secondary_class)

    def test_register_primary_provider_rejects_non_class(self, monkeypatch):
        """Primary registration rejects non-class objects."""
        import modules.groups.providers as providers

        providers._primary_discovered.clear()

        decorator = providers.register_primary_provider("bad_primary")

        with pytest.raises(TypeError, match="must be applied to a class"):
            decorator("not a class")

    def test_register_primary_provider_duplicate_raises(
        self, monkeypatch, mock_primary_class
    ):
        """Registering duplicate primary provider name raises error."""
        import modules.groups.providers as providers

        providers._primary_discovered.clear()

        decorator1 = providers.register_primary_provider("duplicate")
        decorator1(mock_primary_class)

        # Create another mock class
        class AnotherPrimary(mock_primary_class):
            pass

        decorator2 = providers.register_primary_provider("duplicate")

        with pytest.raises(RuntimeError, match="already discovered"):
            decorator2(AnotherPrimary)

    def test_register_secondary_provider_success(
        self, monkeypatch, mock_secondary_class
    ):
        """Secondary provider can be registered with decorator."""
        import modules.groups.providers as providers

        providers._secondary_discovered.clear()

        decorator = providers.register_secondary_provider("test_secondary")
        result = decorator(mock_secondary_class)

        assert "test_secondary" in providers._secondary_discovered
        assert providers._secondary_discovered["test_secondary"] is mock_secondary_class
        assert result is mock_secondary_class

    def test_register_secondary_provider_rejects_non_class(self, monkeypatch):
        """Secondary registration rejects non-class objects."""
        import modules.groups.providers as providers

        providers._secondary_discovered.clear()

        decorator = providers.register_secondary_provider("bad_secondary")

        with pytest.raises(TypeError, match="must be applied to a class"):
            decorator("not a class")

    def test_register_provider_auto_detects_primary(
        self, monkeypatch, mock_primary_class
    ):
        """Auto-detect decorator registers primary when appropriate."""
        import modules.groups.providers as providers

        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()

        # Create a real PrimaryGroupProvider subclass
        class RealPrimary(mock_primary_class):
            """Real primary for auto-detect testing."""

            pass

        decorator = providers.register_provider("auto_primary")

        # Should go to primary discovery (auto-detected from isinstance check)
        decorator(RealPrimary)
        assert "auto_primary" in providers._primary_discovered

    def test_register_provider_auto_detects_secondary(
        self, monkeypatch, mock_secondary_class
    ):
        """Auto-detect decorator registers secondary when appropriate."""
        import modules.groups.providers as providers

        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()

        # Create a real GroupProvider (but not PrimaryGroupProvider)
        class RealSecondary(mock_secondary_class):
            """Real secondary for auto-detect testing."""

            pass

        decorator = providers.register_provider("auto_secondary")

        decorator(RealSecondary)
        assert "auto_secondary" in providers._secondary_discovered


class TestProviderActivation:
    """Tests for single-stage provider activation with config passing."""

    def test_activate_single_primary_provider(
        self,
        monkeypatch,
        mock_primary_class,
        single_primary_config,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """Single primary provider can be activated with config."""
        import modules.groups.providers as providers

        # Setup
        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._primary_active = None
        providers._secondary_active.clear()

        providers._primary_discovered["google"] = mock_primary_class

        # Mock settings with provider config
        mock_settings = mock_settings_groups
        mock_settings.groups.providers = single_primary_config
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        # Activate
        primary_name = providers.activate_providers()

        # Verify
        assert primary_name == "google"
        assert providers._primary_active is not None
        assert isinstance(providers._primary_active, mock_primary_class)
        assert providers._primary_active.name == "google"

    def test_activate_with_config_passed_to_init(
        self,
        monkeypatch,
        mock_primary_class,
        single_primary_config,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """Provider config is passed to __init__ during activation."""
        import modules.groups.providers as providers

        # Setup
        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()

        providers._primary_discovered["google"] = mock_primary_class

        # Mock settings
        mock_settings = mock_settings_groups
        mock_settings.groups.providers = single_primary_config
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        # Activate
        providers.activate_providers()

        # Verify config was passed to instance
        instance = providers._primary_active
        assert instance._config == single_primary_config["google"]

    def test_activate_primary_requires_provides_role_info(
        self,
        monkeypatch,
        mock_settings_groups,
        patch_provider_base_settings,
        mock_primary_class,
    ):
        """Primary provider must have provides_role_info capability."""
        import modules.groups.providers as providers

        # Create primary without role info - must be PrimaryGroupProvider subclass
        class BadPrimary(mock_primary_class):
            """Primary that doesn't provide role info."""

            @property
            def capabilities(self):
                from modules.groups.providers.contracts import ProviderCapabilities

                return ProviderCapabilities(
                    is_primary=True,
                    provides_role_info=False,  # Missing required capability
                    supports_member_management=True,
                )

        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()

        providers._primary_discovered["bad"] = BadPrimary

        # Mock settings - use "bad" to match the registered provider
        mock_settings = mock_settings_groups
        mock_settings.groups.providers = {"bad": {"enabled": True}}
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        # Should raise
        with pytest.raises(RuntimeError, match="must provide role info"):
            providers.activate_providers()

    def test_activate_no_primary_raises(
        self,
        monkeypatch,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """Activation fails if no primary provider is enabled."""
        import modules.groups.providers as providers

        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()

        # Mock settings with no primary
        mock_settings = mock_settings_groups
        mock_settings.groups.providers = {}
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        # Should raise
        with pytest.raises(RuntimeError, match="exactly 1 enabled primary"):
            providers.activate_providers()

    def test_activate_multiple_primaries_raises(
        self,
        monkeypatch,
        mock_primary_class,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """Activation fails if multiple primary providers are enabled."""
        import modules.groups.providers as providers

        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()

        providers._primary_discovered["google"] = mock_primary_class

        class AnotherPrimary(mock_primary_class):
            pass

        providers._primary_discovered["azure"] = AnotherPrimary

        # Mock settings with multiple primaries
        mock_settings = mock_settings_groups
        mock_settings.groups.providers = {
            "google": {"enabled": True},
            "azure": {"enabled": True},
        }
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        # Should raise
        with pytest.raises(RuntimeError, match="exactly 1 enabled primary"):
            providers.activate_providers()

    def test_activate_secondary_providers(
        self,
        monkeypatch,
        mock_primary_class,
        mock_secondary_class,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """Multiple secondary providers can be activated alongside primary."""
        import modules.groups.providers as providers

        # Setup registries
        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()

        providers._primary_discovered["google"] = mock_primary_class
        providers._secondary_discovered["aws"] = mock_secondary_class

        class AzureSecondary(mock_secondary_class):
            pass

        providers._secondary_discovered["azure"] = AzureSecondary

        # Mock settings with primary and secondaries
        mock_settings = mock_settings_groups
        mock_settings.groups.providers = {
            "google": {"enabled": True},
            "aws": {"enabled": True, "prefix": "aws"},
            "azure": {"enabled": True, "prefix": "azure"},
        }
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        # Activate
        primary_name = providers.activate_providers()

        # Verify
        assert primary_name == "google"
        assert providers._primary_active is not None
        assert len(providers._secondary_active) == 2
        assert "aws" in providers._secondary_active
        assert "azure" in providers._secondary_active

    def test_activate_respects_enabled_flag(
        self,
        monkeypatch,
        mock_primary_class,
        mock_secondary_class,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """Disabled providers are skipped during activation."""
        import modules.groups.providers as providers

        # Setup
        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()

        providers._primary_discovered["google"] = mock_primary_class
        providers._secondary_discovered["aws"] = mock_secondary_class

        # Mock settings with disabled secondary
        mock_settings = mock_settings_groups
        mock_settings.groups.providers = {
            "google": {"enabled": True},
            "aws": {"enabled": False},
        }
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        # Activate
        providers.activate_providers()

        # Verify aws was skipped
        assert len(providers._secondary_active) == 0


class TestProviderAccessors:
    """Tests for registry accessor functions."""

    def test_get_primary_provider(
        self,
        monkeypatch,
        mock_primary_class,
        single_primary_config,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """get_primary_provider returns active primary instance."""
        import modules.groups.providers as providers

        # Setup and activate
        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()

        providers._primary_discovered["google"] = mock_primary_class

        mock_settings = mock_settings_groups
        mock_settings.groups.providers = single_primary_config
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        providers.activate_providers()

        # Test accessor
        primary = providers.get_primary_provider()

        assert primary is providers._primary_active
        assert isinstance(primary, mock_primary_class)

    def test_get_primary_provider_no_active_raises(self, monkeypatch):
        """get_primary_provider raises if no primary is active."""
        import modules.groups.providers as providers

        providers._primary_active = None

        with pytest.raises(ValueError, match="No primary provider set"):
            providers.get_primary_provider()

    def test_get_primary_provider_name(
        self,
        monkeypatch,
        mock_primary_class,
        single_primary_config,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """get_primary_provider_name returns the active primary name."""
        import modules.groups.providers as providers

        # Setup
        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()
        providers._PRIMARY_PROVIDER_NAME = None

        providers._primary_discovered["google"] = mock_primary_class

        mock_settings = mock_settings_groups
        mock_settings.groups.providers = single_primary_config
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        providers.activate_providers()

        # Test accessor
        name = providers.get_primary_provider_name()
        assert name == "google"

    def test_get_provider_by_name(
        self,
        monkeypatch,
        mock_primary_class,
        mock_secondary_class,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """get_provider returns provider instance by name."""
        import modules.groups.providers as providers

        # Setup
        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()
        providers._PRIMARY_PROVIDER_NAME = None

        providers._primary_discovered["google"] = mock_primary_class
        providers._secondary_discovered["aws"] = mock_secondary_class

        mock_settings = mock_settings_groups
        mock_settings.groups.providers = {
            "google": {"enabled": True},
            "aws": {"enabled": True},
        }
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        providers.activate_providers()

        # Test accessors
        google = providers.get_provider("google")
        aws = providers.get_provider("aws")

        assert isinstance(google, mock_primary_class)
        assert isinstance(aws, mock_secondary_class)

    def test_get_provider_unknown_raises(self, monkeypatch):
        """get_provider raises for unknown provider name."""
        import modules.groups.providers as providers

        providers._primary_active = None
        providers._secondary_active.clear()

        with pytest.raises(ValueError, match="Unknown provider"):
            providers.get_provider("unknown")

    def test_get_secondary_providers(
        self,
        monkeypatch,
        mock_primary_class,
        mock_secondary_class,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """get_secondary_providers returns dict of all active secondaries."""
        import modules.groups.providers as providers

        # Setup
        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()

        providers._primary_discovered["google"] = mock_primary_class
        providers._secondary_discovered["aws"] = mock_secondary_class

        class AzureSecondary(mock_secondary_class):
            pass

        providers._secondary_discovered["azure"] = AzureSecondary

        mock_settings = mock_settings_groups
        mock_settings.groups.providers = {
            "google": {"enabled": True},
            "aws": {"enabled": True},
            "azure": {"enabled": True},
        }
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        providers.activate_providers()

        # Test accessor
        secondaries = providers.get_secondary_providers()

        assert len(secondaries) == 2
        assert "aws" in secondaries
        assert "azure" in secondaries
        assert isinstance(secondaries["aws"], mock_secondary_class)

    def test_get_active_providers_combined(
        self,
        monkeypatch,
        mock_primary_class,
        mock_secondary_class,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """get_active_providers returns combined primary and secondary view."""
        import modules.groups.providers as providers

        # Setup
        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()
        providers._PRIMARY_PROVIDER_NAME = None

        providers._primary_discovered["google"] = mock_primary_class
        providers._secondary_discovered["aws"] = mock_secondary_class

        mock_settings = mock_settings_groups
        mock_settings.groups.providers = {
            "google": {"enabled": True},
            "aws": {"enabled": True},
        }
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        providers.activate_providers()

        # Test accessor
        all_providers = providers.get_active_providers()

        assert len(all_providers) == 2
        assert "google" in all_providers
        assert "aws" in all_providers

    def test_reset_registry(
        self,
        monkeypatch,
        mock_primary_class,
        single_primary_config,
        mock_settings_groups,
        patch_provider_base_settings,
    ):
        """reset_registry clears all active providers and names."""
        import modules.groups.providers as providers

        # Setup and activate
        providers._primary_discovered.clear()
        providers._secondary_discovered.clear()
        providers._primary_active = None
        providers._secondary_active.clear()
        providers._PRIMARY_PROVIDER_NAME = None

        providers._primary_discovered["google"] = mock_primary_class

        mock_settings = mock_settings_groups
        mock_settings.groups.providers = single_primary_config
        monkeypatch.setattr(
            "infrastructure.configuration.settings",
            mock_settings,
            raising=False,
        )

        providers.activate_providers()

        # Verify activated
        assert providers._primary_active is not None
        assert providers._PRIMARY_PROVIDER_NAME is not None

        # Reset
        providers.reset_registry()

        # Verify cleared
        assert providers._primary_active is None
        assert providers._secondary_active == {}
        assert providers._PRIMARY_PROVIDER_NAME is None
