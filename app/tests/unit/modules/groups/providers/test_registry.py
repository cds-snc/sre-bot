"""Unit tests for groups provider registry.

Tests provider registration (discovery), activation, primary determination,
and registry queries with proper isolation between tests.
"""

import pytest

from modules.groups.providers import (
    register_provider,
    activate_providers,
    get_provider,
    get_active_providers,
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


class MockProvider(GroupProvider):
    """Mock provider for testing."""

    def __init__(self, provides_role_info=False, is_primary=False):
        self._circuit_breaker = None
        self._capabilities = ProviderCapabilities(
            provides_role_info=provides_role_info,
            is_primary=is_primary,
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


class TestProviderRegistration:
    """Test @register_provider decorator."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_register_provider_class(self):
        """@register_provider registers a provider class."""

        @register_provider("test")
        class TestProvider(GroupProvider):
            pass

        assert "test" in DISCOVERED_PROVIDER_CLASSES
        assert DISCOVERED_PROVIDER_CLASSES["test"] is TestProvider

    def test_register_provider_returns_class(self):
        """@register_provider returns the original class."""

        class OriginalProvider(GroupProvider):
            pass

        registered = register_provider("test")(OriginalProvider)
        assert registered is OriginalProvider

    def test_register_provider_must_be_class(self):
        """@register_provider raises TypeError if applied to non-class."""
        with pytest.raises(TypeError):
            register_provider("test")(lambda x: x)

    def test_register_provider_must_subclass_groupprovider(self):
        """@register_provider raises TypeError if not GroupProvider subclass."""

        class NotAProvider:
            pass

        with pytest.raises(TypeError):
            register_provider("test")(NotAProvider)

    def test_register_provider_duplicate_raises(self):
        """@register_provider raises RuntimeError on duplicate names."""

        @register_provider("test")
        class TestProvider1(GroupProvider):
            pass

        with pytest.raises(RuntimeError):

            @register_provider("test")
            class TestProvider2(GroupProvider):
                pass

    def test_register_multiple_providers(self):
        """Multiple providers can be registered."""

        @register_provider("p1")
        class P1(GroupProvider):
            pass

        @register_provider("p2")
        class P2(GroupProvider):
            pass

        assert len(DISCOVERED_PROVIDER_CLASSES) == 2
        assert "p1" in DISCOVERED_PROVIDER_CLASSES
        assert "p2" in DISCOVERED_PROVIDER_CLASSES


class TestProviderActivation:
    """Test activate_providers() and registry population."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_activate_providers_instantiates_discovered(self, groups_providers):
        """activate_providers instantiates discovered provider classes."""

        @register_provider("test")
        class TestProvider(MockProvider):
            def __init__(self):
                super().__init__(provides_role_info=True, is_primary=True)

        groups_providers.set_providers({"test": {"enabled": True}})
        activate_providers()

        assert "test" in PROVIDER_REGISTRY
        assert isinstance(PROVIDER_REGISTRY["test"], TestProvider)

    def test_activate_providers_respects_enabled_false(self, groups_providers):
        """activate_providers skips providers with enabled=False."""

        @register_provider("disabled")
        class DisabledProvider(MockProvider):
            pass

        @register_provider("enabled")
        class EnabledProvider(MockProvider):
            def __init__(self):
                super().__init__(provides_role_info=True, is_primary=True)

        groups_providers.set_providers(
            {
                "disabled": {"enabled": False},
                "enabled": {"enabled": True},
            }
        )
        activate_providers()

        assert "enabled" in PROVIDER_REGISTRY
        assert "disabled" not in PROVIDER_REGISTRY

    def test_activate_providers_default_enabled_true(self, groups_providers):
        """activate_providers treats unconfigured providers as enabled by default."""

        @register_provider("test")
        class TestProvider(MockProvider):
            def __init__(self):
                super().__init__(provides_role_info=True, is_primary=True)

        # Provider config not in dict, but defaults to enabled
        groups_providers.set_providers({})
        activate_providers()

        # Should still be activated (defaults to enabled)
        assert "test" in PROVIDER_REGISTRY

    def test_activate_providers_empty_discovered_raises(self, groups_providers):
        """activate_providers raises if no providers discovered."""
        groups_providers.set_providers({})

        with pytest.raises(ValueError):
            activate_providers()

    def test_activate_providers_clears_previous_registry(self, groups_providers):
        """activate_providers clears old registry entries."""

        @register_provider("test")
        class TestProvider(MockProvider):
            def __init__(self):
                super().__init__(provides_role_info=True, is_primary=True)

        groups_providers.set_providers({"test": {"enabled": True}})

        # First activation
        activate_providers()
        first_instance = PROVIDER_REGISTRY["test"]

        # Second activation
        activate_providers()
        second_instance = PROVIDER_REGISTRY["test"]

        # Should be different instances
        assert first_instance is not second_instance


class TestPrimaryProviderDetermination:
    """Test primary provider selection."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_primary_from_capabilities(self, groups_providers):
        """Primary provider selected from is_primary capability."""

        @register_provider("primary")
        class PrimaryProvider(MockProvider):
            def __init__(self):
                super().__init__(provides_role_info=True, is_primary=True)

        @register_provider("secondary")
        class SecondaryProvider(MockProvider):
            def __init__(self):
                super().__init__(provides_role_info=True, is_primary=False)

        groups_providers.set_providers(
            {
                "primary": {"enabled": True},
                "secondary": {"enabled": True},
            }
        )
        activate_providers()

        # Should select primary provider
        from modules.groups.providers import _PRIMARY_PROVIDER_NAME

        assert _PRIMARY_PROVIDER_NAME == "primary"

    def test_primary_single_provider_becomes_primary(self, groups_providers):
        """Single enabled provider automatically becomes primary."""

        @register_provider("only")
        class OnlyProvider(MockProvider):
            def __init__(self):
                super().__init__(provides_role_info=True)

        groups_providers.set_providers({"only": {"enabled": True}})
        activate_providers()

        from modules.groups.providers import _PRIMARY_PROVIDER_NAME

        assert _PRIMARY_PROVIDER_NAME == "only"

    def test_primary_multiple_with_none_marked_raises(self, groups_providers):
        """Multiple providers with none marked primary raises ValueError."""

        @register_provider("p1")
        class P1(MockProvider):
            def __init__(self):
                super().__init__(provides_role_info=True)

        @register_provider("p2")
        class P2(MockProvider):
            def __init__(self):
                super().__init__(provides_role_info=True)

        groups_providers.set_providers(
            {
                "p1": {"enabled": True},
                "p2": {"enabled": True},
            }
        )

        with pytest.raises(ValueError):
            activate_providers()


class TestGetProvider:
    """Test get_provider() function."""

    def setup_method(self):
        """Clear registry before each test."""
        PROVIDER_REGISTRY.clear()

    def test_get_provider_returns_provider(self):
        """get_provider returns provider from registry."""
        provider = MockProvider()
        PROVIDER_REGISTRY["test"] = provider

        result = get_provider("test")
        assert result is provider

    def test_get_provider_unknown_raises(self):
        """get_provider raises ValueError for unknown provider."""
        PROVIDER_REGISTRY.clear()

        with pytest.raises(ValueError):
            get_provider("nonexistent")

    def test_get_provider_multiple_in_registry(self):
        """get_provider finds correct provider when multiple registered."""
        p1 = MockProvider()
        p2 = MockProvider()
        p3 = MockProvider()

        PROVIDER_REGISTRY["p1"] = p1
        PROVIDER_REGISTRY["p2"] = p2
        PROVIDER_REGISTRY["p3"] = p3

        assert get_provider("p1") is p1
        assert get_provider("p2") is p2
        assert get_provider("p3") is p3


class TestGetActiveProviders:
    """Test get_active_providers() function."""

    def setup_method(self):
        """Clear registry before each test."""
        PROVIDER_REGISTRY.clear()

    def test_get_active_providers_all_when_no_filter(self):
        """get_active_providers returns all when no filter provided."""
        p1 = MockProvider()
        p2 = MockProvider()

        PROVIDER_REGISTRY["p1"] = p1
        PROVIDER_REGISTRY["p2"] = p2

        result = get_active_providers()
        assert len(result) == 2
        assert result["p1"] is p1
        assert result["p2"] is p2

    def test_get_active_providers_single_when_filter(self):
        """get_active_providers returns single provider when filtered."""
        p1 = MockProvider()
        p2 = MockProvider()

        PROVIDER_REGISTRY["p1"] = p1
        PROVIDER_REGISTRY["p2"] = p2

        result = get_active_providers(provider_filter="p1")
        assert len(result) == 1
        assert result["p1"] is p1
        assert "p2" not in result

    def test_get_active_providers_empty_registry(self):
        """get_active_providers returns empty dict for empty registry."""
        PROVIDER_REGISTRY.clear()

        result = get_active_providers()
        assert result == {}

    def test_get_active_providers_filter_not_found_raises(self):
        """get_active_providers raises ValueError when filter provider not found."""
        PROVIDER_REGISTRY["p1"] = MockProvider()

        with pytest.raises(ValueError):
            get_active_providers(provider_filter="p2")


class TestValidateStartupConfiguration:
    """Test _validate_startup() function."""

    def setup_method(self):
        """Clear registry before each test."""
        PROVIDER_REGISTRY.clear()

    def test_validate_startup_primary_not_in_registry_raises(self):
        """_validate_startup raises if primary not in registry."""
        from modules.groups.providers import _validate_startup

        PROVIDER_REGISTRY.clear()

        with pytest.raises(RuntimeError):
            _validate_startup("primary")

    def test_validate_startup_primary_missing_role_info_raises(self):
        """_validate_startup raises if primary doesn't provide role info."""
        from modules.groups.providers import _validate_startup

        provider = MockProvider(provides_role_info=False)
        PROVIDER_REGISTRY["primary"] = provider

        with pytest.raises(RuntimeError):
            _validate_startup("primary")

    def test_validate_startup_primary_with_role_info_passes(self):
        """_validate_startup passes if primary provides role info."""
        from modules.groups.providers import _validate_startup

        provider = MockProvider(provides_role_info=True)
        PROVIDER_REGISTRY["primary"] = provider

        # Should not raise
        _validate_startup("primary")

    def test_validate_startup_empty_primary_name_raises(self):
        """_validate_startup raises if primary name is empty string."""
        from modules.groups.providers import _validate_startup

        with pytest.raises(RuntimeError):
            _validate_startup("")


class TestProviderDiscoveryIsolation:
    """Test isolation of provider discovery between test runs."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_discovered_classes_isolated(self):
        """Discovered classes don't leak between tests."""
        assert len(DISCOVERED_PROVIDER_CLASSES) == 0

        @register_provider("test1")
        class TestProvider(MockProvider):
            pass

        assert len(DISCOVERED_PROVIDER_CLASSES) == 1

    def test_provider_registry_isolated(self):
        """Provider registry doesn't leak between tests."""
        assert len(PROVIDER_REGISTRY) == 0

        provider = MockProvider()
        PROVIDER_REGISTRY["test"] = provider

        assert len(PROVIDER_REGISTRY) == 1


class TestProviderActivationErrors:
    """Test error handling during provider activation."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_activate_provider_instantiation_error(self, groups_providers):
        """activate_providers handles instantiation errors gracefully."""

        @register_provider("broken")
        class BrokenProvider(GroupProvider):
            def __init__(self):
                raise RuntimeError("Initialization failed")

        groups_providers.set_providers({"broken": {"enabled": True}})

        with pytest.raises(RuntimeError):
            activate_providers()

    def test_activate_all_disabled_raises(self, groups_providers):
        """activate_providers raises if all discovered providers disabled."""

        @register_provider("p1")
        class P1(MockProvider):
            pass

        @register_provider("p2")
        class P2(MockProvider):
            pass

        groups_providers.set_providers(
            {
                "p1": {"enabled": False},
                "p2": {"enabled": False},
            }
        )

        with pytest.raises(ValueError):
            activate_providers()


class TestProviderCapabilities:
    """Test provider capabilities handling."""

    def setup_method(self):
        """Clear registries before each test."""
        DISCOVERED_PROVIDER_CLASSES.clear()
        PROVIDER_REGISTRY.clear()

    def test_provider_with_none_capabilities(self, groups_providers):
        """Single provider with None capabilities becomes primary."""

        class NoneCapProvider(GroupProvider):
            def __init__(self):
                # Must provide minimal circuit breaker config
                self._circuit_breaker = None

            @property
            def capabilities(self):
                return None

            def _get_group_members_impl(self, group_key: str, **kwargs):
                raise NotImplementedError()

            def _add_member_impl(self, group_key: str, member_data, justification: str):
                raise NotImplementedError()

            def _remove_member_impl(
                self, group_key: str, member_data, justification: str
            ):
                raise NotImplementedError()

            def list_groups_for_user(self, user_key: str, **kwargs):
                raise NotImplementedError()

            def create_user(self, user_data):
                raise NotImplementedError()

            def delete_user(self, user_key: str):
                raise NotImplementedError()

            def _list_groups_impl(self, **kwargs):
                raise NotImplementedError()

            def _list_groups_with_members_impl(self, **kwargs):
                raise NotImplementedError()

        register_provider("none_cap")(NoneCapProvider)

        groups_providers.set_providers({"none_cap": {"enabled": True}})

        # Single provider (regardless of capabilities) becomes primary
        activate_providers()
        assert "none_cap" in PROVIDER_REGISTRY
