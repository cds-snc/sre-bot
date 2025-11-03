"""Integration tests for configuration-driven provider activation.

Tests recommendation_02 implementation: Configuration-Driven Provider Activation
with support for:
- Enabling/disabling providers via config (enabled=True/False)
- Prefix overrides from config
- Capability overrides from config
- Primary provider validation with disabled providers
"""

import pytest
from modules.groups.providers.base import (
    GroupProvider,
    ProviderCapabilities,
    OperationResult,
    OperationStatus,
)
from modules.groups.models import NormalizedMember
from typing import Optional


class FakeProvider(GroupProvider):
    """Minimal test provider for configuration testing.

    Note: Named FakeProvider instead of TestProvider to avoid pytest collection
    warnings about test classes with __init__ constructors.
    """

    def __init__(self):
        self._capabilities = ProviderCapabilities(
            supports_member_management=True, provides_role_info=False
        )

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Return the instance capabilities directly (not via get_capabilities)
        # to avoid recursion during activation
        return self._capabilities

    def get_group_members(self, group_key: str, **kwargs) -> OperationResult:
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})

    def add_member(
        self, group_key: str, member_data, justification: str = ""
    ) -> OperationResult:
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def remove_member(
        self, group_key: str, member_data, justification: str = ""
    ) -> OperationResult:
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def list_groups_for_user(
        self, user_key: str, provider_name: Optional[str] = None, **kwargs
    ) -> OperationResult:
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})

    def create_user(self, user_data: NormalizedMember) -> OperationResult:
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def delete_user(self, user_key: str) -> OperationResult:
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def list_groups(self, **kwargs) -> OperationResult:
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})

    def list_groups_with_members(self, **kwargs) -> OperationResult:
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})


class FakePrimaryProvider(FakeProvider):
    """Test provider with is_primary capability.

    Note: Named FakePrimaryProvider instead of TestPrimaryProvider to avoid pytest
    collection warnings about test classes with __init__ constructors.
    """

    def __init__(self):
        super().__init__()
        self._capabilities = ProviderCapabilities(
            supports_member_management=True, provides_role_info=True, is_primary=True
        )


class TestEnabledDisabledFiltering:
    """Test that disabled providers are filtered out during activation."""

    def test_single_enabled_provider_activates(
        self, safe_providers_import, single_provider_config
    ):
        """Test that a single enabled provider is activated successfully."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register test provider
        mod.register_provider("google")(FakePrimaryProvider)

        # Configure via single_provider_config fixture
        from core.config import settings

        settings.groups.providers = single_provider_config

        # Activate providers
        primary = mod.activate_providers()

        assert primary == "google"
        assert "google" in mod.PROVIDER_REGISTRY
        assert len(mod.PROVIDER_REGISTRY) == 1

    def test_disabled_provider_not_activated(
        self, safe_providers_import, disabled_provider_config
    ):
        """Test that disabled providers are excluded from activation."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register both providers
        mod.register_provider("google")(FakePrimaryProvider)
        mod.register_provider("aws")(FakeProvider)

        # Configure with one disabled
        from core.config import settings

        settings.groups.providers = disabled_provider_config

        # Activate providers
        primary = mod.activate_providers()

        assert primary == "google"
        assert "google" in mod.PROVIDER_REGISTRY
        assert (
            "aws" not in mod.PROVIDER_REGISTRY
        )  # Disabled provider should not be activated
        assert len(mod.PROVIDER_REGISTRY) == 1

    def test_multi_provider_all_enabled(
        self, safe_providers_import, multi_provider_config
    ):
        """Test that multiple enabled providers are all activated."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register both providers
        mod.register_provider("google")(FakePrimaryProvider)
        mod.register_provider("aws")(FakeProvider)

        # Configure with both enabled
        from core.config import settings

        settings.groups.providers = multi_provider_config

        # Activate providers
        primary = mod.activate_providers()

        assert primary == "google"
        assert "google" in mod.PROVIDER_REGISTRY
        assert "aws" in mod.PROVIDER_REGISTRY
        assert len(mod.PROVIDER_REGISTRY) == 2

    def test_all_providers_disabled_raises_error(
        self, safe_providers_import, mock_provider_config
    ):
        """Test that disabling all providers raises an appropriate error."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register provider
        mod.register_provider("google")(FakeProvider)

        # Configure as disabled
        from core.config import settings

        settings.groups.providers = {"google": {"enabled": False}}

        # Activation should fail - no enabled providers
        with pytest.raises(ValueError, match="sole provider.*is disabled"):
            mod.activate_providers()


class TestPrefixOverrides:
    """Test that prefix overrides from config are applied correctly."""

    def test_prefix_override_applied(self, safe_providers_import, mock_provider_config):
        """Test that config prefix override takes precedence over provider default."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register provider
        mod.register_provider("aws")(FakeProvider)

        # Configure with custom prefix
        from core.config import settings

        settings.groups.providers = {
            "aws": {
                "enabled": True,
                "prefix": "custom_aws_prefix",
                "capabilities": {"is_primary": True, "provides_role_info": True},
            }
        }

        # Activate and check prefix
        mod.activate_providers()

        provider = mod.PROVIDER_REGISTRY["aws"]
        assert hasattr(provider, "_prefix")
        assert provider._prefix == "custom_aws_prefix"

    def test_default_prefix_when_not_overridden(
        self, safe_providers_import, single_provider_config
    ):
        """Test that default prefix is used when no override is provided."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register provider with default prefix
        mod.register_provider("google")(FakePrimaryProvider)

        # Configure without prefix override
        from core.config import settings

        settings.groups.providers = single_provider_config

        # Activate and check prefix
        mod.activate_providers()

        provider = mod.PROVIDER_REGISTRY["google"]
        assert hasattr(provider, "_prefix")
        # Default prefix should be provider name
        assert provider._prefix == "google"


class TestCapabilityOverrides:
    """Test that capability overrides from config are merged correctly."""

    def test_capability_override_merged_with_defaults(
        self, safe_providers_import, mock_provider_config
    ):
        """Test that config capabilities are merged with provider defaults."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register provider
        mod.register_provider("test")(FakeProvider)

        # Configure with capability overrides
        from core.config import settings

        settings.groups.providers = {
            "test": {
                "enabled": True,
                "capabilities": {
                    "is_primary": True,
                    "provides_role_info": True,  # Override default False
                    "supports_batch_operations": True,
                    "max_batch_size": 50,
                },
            }
        }

        # Activate and check capabilities
        mod.activate_providers()

        provider = mod.PROVIDER_REGISTRY["test"]
        caps = provider.get_capabilities()

        # Overridden capabilities
        assert caps.is_primary is True
        assert caps.provides_role_info is True
        assert caps.supports_batch_operations is True
        assert caps.max_batch_size == 50

        # Provider default capabilities should still be present
        assert caps.supports_member_management is True

    def test_capability_override_via_get_capabilities(
        self, safe_providers_import, mock_provider_config
    ):
        """Test that get_capabilities() returns merged capabilities."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register provider
        mod.register_provider("test")(FakeProvider)

        # Configure with capability override
        from core.config import settings

        settings.groups.providers = {
            "test": {
                "enabled": True,
                "capabilities": {
                    "is_primary": True,
                    "provides_role_info": True,
                    "max_batch_size": 100,
                },
            }
        }

        # Activate
        mod.activate_providers()

        provider = mod.PROVIDER_REGISTRY["test"]

        # Check via get_capabilities() (should return override)
        caps = provider.get_capabilities()
        assert caps.provides_role_info is True
        assert caps.max_batch_size == 100

    def test_no_capability_override_uses_provider_defaults(
        self, safe_providers_import, single_provider_config
    ):
        """Test that provider defaults are used when no overrides are specified."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register provider
        mod.register_provider("google")(FakePrimaryProvider)

        # Configure without capability overrides
        from core.config import settings

        settings.groups.providers = single_provider_config

        # Activate
        mod.activate_providers()

        provider = mod.PROVIDER_REGISTRY["google"]
        caps = provider.get_capabilities()

        # Should have provider's default capabilities
        assert caps.is_primary is True
        assert caps.provides_role_info is True
        assert caps.supports_member_management is True


class TestPrimaryProviderValidation:
    """Test that primary provider validation respects disabled providers."""

    def test_disabled_sole_provider_raises_error(
        self, safe_providers_import, mock_provider_config
    ):
        """Test that a disabled sole provider raises an error during primary determination."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register single provider
        mod.register_provider("google")(FakeProvider)

        # Configure as disabled
        from core.config import settings

        settings.groups.providers = {"google": {"enabled": False}}

        # Should raise because no enabled providers
        with pytest.raises(ValueError, match="sole provider.*is disabled"):
            mod.activate_providers()

    def test_primary_provider_must_be_enabled(
        self, safe_providers_import, mock_provider_config
    ):
        """Test that the primary provider must be enabled."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register two providers
        mod.register_provider("google")(FakePrimaryProvider)
        mod.register_provider("aws")(FakeProvider)

        # Configure google as primary but disabled
        from core.config import settings

        settings.groups.providers = {
            "google": {"enabled": False, "primary": True},
            "aws": {"enabled": True, "prefix": "aws"},
        }

        # Should work because google is filtered out before activation
        # and aws becomes the sole provider, making it primary
        primary = mod.activate_providers()
        assert primary == "aws"
        assert "google" not in mod.PROVIDER_REGISTRY
        assert "aws" in mod.PROVIDER_REGISTRY


class TestConfigurationIntegration:
    """Integration tests for complete configuration scenarios."""

    def test_config_validation_enforces_one_primary(
        self, safe_providers_import, mock_provider_config
    ):
        """Test that config validation requires exactly one primary provider among enabled."""
        from core.config import GroupsFeatureSettings

        # Valid: one enabled primary
        config = GroupsFeatureSettings(
            GROUP_PROVIDERS={
                "google": {"enabled": True, "primary": True},
                "aws": {"enabled": True, "prefix": "aws"},
            }
        )
        assert config.providers["google"]["primary"] is True

        # Invalid: no primary provider
        with pytest.raises(ValueError, match="exactly one enabled provider"):
            GroupsFeatureSettings(
                GROUP_PROVIDERS={
                    "google": {"enabled": True},
                    "aws": {"enabled": True, "prefix": "aws"},
                }
            )

        # Invalid: multiple enabled primary providers
        with pytest.raises(ValueError, match="exactly one enabled provider"):
            GroupsFeatureSettings(
                GROUP_PROVIDERS={
                    "google": {"enabled": True, "primary": True},
                    "aws": {"enabled": True, "primary": True, "prefix": "aws"},
                }
            )

    def test_disabled_provider_excluded_from_primary_validation(self):
        """Test that disabled providers are not counted in primary validation."""
        from core.config import GroupsFeatureSettings

        # Valid: one enabled primary, one disabled primary (disabled ignored)
        config = GroupsFeatureSettings(
            GROUP_PROVIDERS={
                "google": {"enabled": True, "primary": True},
                "aws": {"enabled": False, "primary": True, "prefix": "aws"},
            }
        )

        # Should succeed because aws is disabled and not counted
        assert config.providers["google"]["primary"] is True
        assert config.providers["aws"]["enabled"] is False

    def test_complete_multi_provider_scenario(
        self, safe_providers_import, multi_provider_config
    ):
        """Integration test: multi-provider setup with prefix and capability overrides."""
        mod = safe_providers_import
        mod.PROVIDER_REGISTRY.clear()
        mod.DISCOVERED_PROVIDER_CLASSES.clear()

        # Register both providers
        mod.register_provider("google")(FakePrimaryProvider)
        mod.register_provider("aws")(FakeProvider)

        # Configure via fixture
        from core.config import settings

        settings.groups.providers = multi_provider_config

        # Activate
        primary = mod.activate_providers()

        # Verify primary
        assert primary == "google"

        # Verify both activated
        assert "google" in mod.PROVIDER_REGISTRY
        assert "aws" in mod.PROVIDER_REGISTRY

        # Verify prefix overrides
        aws_provider = mod.PROVIDER_REGISTRY["aws"]
        assert aws_provider._prefix == "aws"

        # Verify capability overrides
        aws_caps = aws_provider.get_capabilities()
        assert aws_caps.supports_batch_operations is True
        assert aws_caps.max_batch_size == 100
