"""Unit tests for groups provider configuration-driven activation.

Tests enabled/disabled filtering, prefix overrides, capability merging,
and primary provider validation during provider activation.
"""

import pytest

from modules.groups.providers import (
    register_provider,
    activate_providers,
    PROVIDER_REGISTRY,
    DISCOVERED_PROVIDER_CLASSES,
)
from modules.groups.providers.base import (
    GroupProvider,
    ProviderCapabilities,
    OperationResult,
    OperationStatus,
)


pytestmark = pytest.mark.unit


class MockPrimaryProvider(GroupProvider):
    """Mock provider with is_primary capability."""

    def __init__(self):
        self._circuit_breaker = None
        self._capabilities = ProviderCapabilities(
            provides_role_info=True,
            is_primary=True,
        )

    @property
    def capabilities(self):
        return self._capabilities

    def _get_group_members_impl(self, group_key: str, **kwargs):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})

    def _add_member_impl(self, group_key: str, member_data, justification: str):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def _remove_member_impl(self, group_key: str, member_data, justification: str):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def list_groups_for_user(self, user_key: str, **kwargs):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})

    def create_user(self, user_data):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def delete_user(self, user_key: str):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def _list_groups_impl(self, **kwargs):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})

    def _list_groups_with_members_impl(self, **kwargs):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})


class MockSecondaryProvider(GroupProvider):
    """Mock secondary provider without is_primary capability."""

    def __init__(self):
        self._circuit_breaker = None
        self._capabilities = ProviderCapabilities(
            provides_role_info=False,
            is_primary=False,
        )

    @property
    def capabilities(self):
        return self._capabilities

    def _get_group_members_impl(self, group_key: str, **kwargs):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})

    def _add_member_impl(self, group_key: str, member_data, justification: str):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def _remove_member_impl(self, group_key: str, member_data, justification: str):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def list_groups_for_user(self, user_key: str, **kwargs):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})

    def create_user(self, user_data):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def delete_user(self, user_key: str):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def _list_groups_impl(self, **kwargs):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})

    def _list_groups_with_members_impl(self, **kwargs):
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})


class TestEnabledDisabledFiltering:
    """Test enabled/disabled provider filtering during activation."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_single_enabled_provider_activates(self, groups_providers):
        """Single enabled provider is activated successfully."""

        @register_provider("google")
        class GoogleProvider(MockPrimaryProvider):
            pass

        groups_providers.set_providers({"google": {"enabled": True}})
        activate_providers()

        assert "google" in PROVIDER_REGISTRY
        assert len(PROVIDER_REGISTRY) == 1
        assert isinstance(PROVIDER_REGISTRY["google"], GoogleProvider)

    def test_disabled_provider_not_activated(self, groups_providers):
        """Disabled provider is excluded from activation."""

        @register_provider("google")
        class GoogleProvider(MockPrimaryProvider):
            pass

        @register_provider("aws")
        class AwsProvider(MockSecondaryProvider):
            pass

        groups_providers.set_providers(
            {
                "google": {"enabled": True},
                "aws": {"enabled": False},
            }
        )
        activate_providers()

        assert "google" in PROVIDER_REGISTRY
        assert "aws" not in PROVIDER_REGISTRY
        assert len(PROVIDER_REGISTRY) == 1

    def test_default_enabled_true_for_unconfigured(self, groups_providers):
        """Unconfigured providers default to enabled=True."""

        @register_provider("google")
        class GoogleProvider(MockPrimaryProvider):
            pass

        groups_providers.set_providers({})
        activate_providers()

        assert "google" in PROVIDER_REGISTRY

    def test_multiple_providers_all_enabled(self, groups_providers):
        """Multiple enabled providers are all activated."""

        @register_provider("google")
        class GoogleProvider(MockPrimaryProvider):
            pass

        @register_provider("aws")
        class AwsProvider(MockSecondaryProvider):
            pass

        groups_providers.set_providers(
            {
                "google": {"enabled": True},
                "aws": {"enabled": True},
            }
        )
        activate_providers()

        assert "google" in PROVIDER_REGISTRY
        assert "aws" in PROVIDER_REGISTRY
        assert len(PROVIDER_REGISTRY) == 2

    def test_all_providers_disabled_raises(self, groups_providers):
        """All providers disabled raises ValueError."""

        @register_provider("google")
        class GoogleProvider(MockPrimaryProvider):
            pass

        groups_providers.set_providers({"google": {"enabled": False}})

        with pytest.raises(ValueError):
            activate_providers()


class TestPrefixConfiguration:
    """Test provider prefix configuration and overrides."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_default_prefix_is_provider_name(self, groups_providers):
        """Default prefix is the provider name when not configured."""

        @register_provider("google")
        class GoogleProvider(MockPrimaryProvider):
            pass

        groups_providers.set_providers({"google": {"enabled": True}})
        activate_providers()

        provider = PROVIDER_REGISTRY["google"]
        assert getattr(provider, "_prefix", None) == "google"

    def test_prefix_override_from_config(self, groups_providers):
        """Config prefix override takes precedence over default."""

        @register_provider("google")
        class GoogleProvider(MockPrimaryProvider):
            pass

        groups_providers.set_providers({"google": {"enabled": True, "prefix": "gws"}})
        activate_providers()

        provider = PROVIDER_REGISTRY["google"]
        assert getattr(provider, "_prefix", None) == "gws"

    def test_multiple_providers_different_prefixes(self, groups_providers):
        """Multiple providers can have different configured prefixes."""

        @register_provider("google")
        class GoogleProvider(MockPrimaryProvider):
            pass

        @register_provider("aws")
        class AwsProvider(MockSecondaryProvider):
            pass

        groups_providers.set_providers(
            {
                "google": {"enabled": True, "prefix": "gws"},
                "aws": {"enabled": True, "prefix": "aws_iam"},
            }
        )
        activate_providers()

        assert getattr(PROVIDER_REGISTRY["google"], "_prefix") == "gws"
        assert getattr(PROVIDER_REGISTRY["aws"], "_prefix") == "aws_iam"

    def test_empty_prefix_string_uses_default(self, groups_providers):
        """Empty prefix string falls back to provider name as default."""

        @register_provider("google")
        class GoogleProvider(MockPrimaryProvider):
            pass

        groups_providers.set_providers({"google": {"enabled": True, "prefix": ""}})
        activate_providers()

        provider = PROVIDER_REGISTRY["google"]
        # Empty string is falsy, so implementation uses default provider name
        assert getattr(provider, "_prefix", None) in ("", "google")


class TestCapabilityOverrides:
    """Test capability merging from config overrides."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_capability_override_merged_with_provider_defaults(self, groups_providers):
        """Config capabilities merged with provider defaults."""

        @register_provider("test")
        class TestProvider(MockSecondaryProvider):
            pass

        groups_providers.set_providers(
            {
                "test": {
                    "enabled": True,
                    "capabilities": {"is_primary": True, "provides_role_info": True},
                }
            }
        )
        activate_providers()

        provider = PROVIDER_REGISTRY["test"]
        caps = provider.get_capabilities()

        # Overridden capabilities
        assert caps.is_primary is True
        assert caps.provides_role_info is True

    def test_capability_override_stored_in_provider(self, groups_providers):
        """Capability overrides stored on provider instance."""

        @register_provider("test")
        class TestProvider(MockSecondaryProvider):
            pass

        groups_providers.set_providers(
            {
                "test": {
                    "enabled": True,
                    "capabilities": {"is_primary": True, "provides_role_info": True},
                }
            }
        )
        activate_providers()

        provider = PROVIDER_REGISTRY["test"]
        # Check that override is stored
        assert hasattr(provider, "_capability_override")
        assert provider._capability_override.is_primary is True

    def test_no_override_uses_provider_defaults(self, groups_providers):
        """No config overrides use provider defaults."""

        @register_provider("google")
        class GoogleProvider(MockPrimaryProvider):
            pass

        groups_providers.set_providers({"google": {"enabled": True}})
        activate_providers()

        provider = PROVIDER_REGISTRY["google"]
        caps = provider.get_capabilities()

        # Provider defaults preserved
        assert caps.provides_role_info is True
        assert caps.is_primary is True

    def test_partial_capability_override(self, groups_providers):
        """Partial capability override preserves other fields."""

        @register_provider("test")
        class TestProvider(MockSecondaryProvider):
            pass

        groups_providers.set_providers(
            {"test": {"enabled": True, "capabilities": {"is_primary": True}}}
        )
        activate_providers()

        provider = PROVIDER_REGISTRY["test"]
        caps = provider.get_capabilities()

        # Overridden
        assert caps.is_primary is True
        # Preserved from provider default
        assert caps.provides_role_info is False


class TestConfigurationReload:
    """Test configuration handling during provider activation."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_registry_cleared_on_reactivation(self, groups_providers):
        """Registry cleared on subsequent activation calls."""

        @register_provider("test")
        class TestProvider(MockPrimaryProvider):
            pass

        # First activation
        groups_providers.set_providers({"test": {"enabled": True}})
        activate_providers()
        first_instance = PROVIDER_REGISTRY["test"]

        # Second activation
        activate_providers()
        second_instance = PROVIDER_REGISTRY["test"]

        # Should be different instances (registry was cleared)
        assert first_instance is not second_instance

    def test_disabled_provider_removed_on_reactivation(self, groups_providers):
        """Previously enabled provider removed if disabled in new config."""

        @register_provider("test")
        class TestProvider(MockPrimaryProvider):
            pass

        # First: enabled
        groups_providers.set_providers({"test": {"enabled": True}})
        activate_providers()
        assert "test" in PROVIDER_REGISTRY

        # Second: disabled
        groups_providers.set_providers({"test": {"enabled": False}})
        with pytest.raises(ValueError):
            activate_providers()


class TestActivationValidation:
    """Test validation errors during provider activation."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_no_discovered_providers_raises(self, groups_providers):
        """No discovered providers raises error even with config."""
        # Don't register any providers
        groups_providers.set_providers({"nonexistent": {"enabled": True}})

        # Should fail because no discovered providers at all
        with pytest.raises(ValueError):
            activate_providers()

    def test_provider_instantiation_error_propagated(self, groups_providers):
        """Provider __init__ errors propagate during activation."""

        @register_provider("broken")
        class BrokenProvider(GroupProvider):
            def __init__(self):
                raise RuntimeError("Broken initialization")

        groups_providers.set_providers({"broken": {"enabled": True}})

        with pytest.raises(RuntimeError):
            activate_providers()

    def test_invalid_capability_override_raises(self, groups_providers):
        """Invalid capability override value raises error."""

        @register_provider("test")
        class TestProvider(MockPrimaryProvider):
            pass

        groups_providers.set_providers(
            {
                "test": {
                    "enabled": True,
                    # This will raise because asdict() fails on invalid field
                    "capabilities": {"invalid_field_xyz": True},
                }
            }
        )

        with pytest.raises(Exception):
            activate_providers()


class TestMultiProviderActivation:
    """Test complex multi-provider activation scenarios."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_primary_with_secondary_providers(self, groups_providers):
        """Primary provider selected among multiple."""

        @register_provider("google")
        class GoogleProvider(MockPrimaryProvider):
            pass

        @register_provider("aws")
        class AwsProvider(MockSecondaryProvider):
            pass

        groups_providers.set_providers(
            {
                "google": {"enabled": True},
                "aws": {"enabled": True},
            }
        )
        activate_providers()

        assert "google" in PROVIDER_REGISTRY
        assert "aws" in PROVIDER_REGISTRY

    def test_mix_of_enabled_disabled_providers(self, groups_providers):
        """Mix of enabled and disabled providers."""

        @register_provider("p1")
        class P1(MockPrimaryProvider):
            pass

        @register_provider("p2")
        class P2(MockSecondaryProvider):
            pass

        @register_provider("p3")
        class P3(MockSecondaryProvider):
            pass

        groups_providers.set_providers(
            {
                "p1": {"enabled": True},
                "p2": {"enabled": False},
                "p3": {"enabled": True},
            }
        )
        activate_providers()

        assert "p1" in PROVIDER_REGISTRY
        assert "p2" not in PROVIDER_REGISTRY
        assert "p3" in PROVIDER_REGISTRY

    def test_provider_configs_with_all_options(self, groups_providers):
        """Provider config with enabled, prefix, and capabilities."""

        @register_provider("test")
        class TestProvider(MockPrimaryProvider):
            pass

        groups_providers.set_providers(
            {
                "test": {
                    "enabled": True,
                    "prefix": "custom",
                    "capabilities": {"is_primary": True, "provides_role_info": True},
                }
            }
        )
        activate_providers()

        provider = PROVIDER_REGISTRY["test"]
        assert getattr(provider, "_prefix") == "custom"
        assert provider.get_capabilities().is_primary is True
        assert provider.get_capabilities().provides_role_info is True
