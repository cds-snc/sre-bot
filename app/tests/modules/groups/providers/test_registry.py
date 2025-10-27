import pytest


def test_register_class_and_instance_and_invalid(
    safe_providers_import, groups_providers
):
    mod = safe_providers_import

    # start with a clean registry
    mod.PROVIDER_REGISTRY.clear()

    from modules.groups.providers.base import (
        GroupProvider,
        OperationResult,
        OperationStatus,
        ProviderCapabilities,
    )

    class DummyProvider(GroupProvider):
        def __init__(self):
            self._capabilities = ProviderCapabilities(provides_role_info=True)

        @property
        def capabilities(self):
            return self._capabilities

        def get_group_members(self, group_key: str, **kwargs) -> OperationResult:
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def add_member(
            self, group_key: str, member_data, justification: str
        ) -> OperationResult:
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def remove_member(
            self, group_key: str, member_data, justification: str
        ) -> OperationResult:
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def get_user_managed_groups(self, user_key: str) -> OperationResult:
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def validate_permissions(
            self, user_key: str, group_key: str, action: str
        ) -> OperationResult:
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def create_user(self, user_data: dict) -> OperationResult:
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def delete_user(self, user_key: str) -> OperationResult:
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def list_groups(self, **kwargs) -> OperationResult:
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def list_groups_with_members(self, **kwargs) -> OperationResult:
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

    # Provide config so non-primary providers may register (require prefix)
    groups_providers.set_providers({"dummy": {"enabled": True, "prefix": "d"}})

    # Register a class (deferred register in conftest will use the
    # current settings when called)
    mod.register_provider("dummy")(DummyProvider)
    assert "dummy" in mod.PROVIDER_REGISTRY
    assert isinstance(mod.PROVIDER_REGISTRY["dummy"], GroupProvider)

    # Register an instance
    mod.PROVIDER_REGISTRY.pop("dummy", None)
    inst = DummyProvider()
    groups_providers.providers["dummy_inst"] = {"enabled": True, "prefix": "di"}
    mod.register_provider("dummy_inst")(inst)
    assert "dummy_inst" in mod.PROVIDER_REGISTRY
    assert mod.PROVIDER_REGISTRY["dummy_inst"] is inst

    # Invalid object registration should raise TypeError
    with pytest.raises(TypeError):
        mod.register_provider("bad")(123)

    # Duplicate registration should raise RuntimeError
    mod.PROVIDER_REGISTRY.clear()
    groups_providers.providers["dup"] = {"enabled": True, "prefix": "dp"}
    mod.register_provider("dup")(DummyProvider)
    with pytest.raises(RuntimeError):
        mod.register_provider("dup")(DummyProvider)


def test_register_skips_when_disabled(safe_providers_import, groups_providers):
    """Provider registration should be skipped when the provider is disabled

    This covers the branch where `register_provider` reads the provider config
    and returns early when `enabled` is False.
    """
    mod = safe_providers_import
    mod.PROVIDER_REGISTRY.clear()

    from modules.groups.providers.base import GroupProvider, ProviderCapabilities

    class DisabledProvider(GroupProvider):
        def __init__(self):
            self._capabilities = ProviderCapabilities(provides_role_info=True)

        @property
        def capabilities(self):
            return self._capabilities

        def get_group_members(self, group_key: str, **kwargs):
            raise NotImplementedError()

        def add_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def remove_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def get_user_managed_groups(self, user_key: str):
            raise NotImplementedError()

        def validate_permissions(self, user_key: str, group_key: str, action: str):
            raise NotImplementedError()

        def create_user(self, user_data: dict):
            raise NotImplementedError()

        def delete_user(self, user_key: str):
            raise NotImplementedError()

        def list_groups(self, **kwargs):
            raise NotImplementedError()
        
        def list_groups_with_members(self, **kwargs):
            raise NotImplementedError()

    # Mark provider as disabled in config
    groups_providers.providers["disabled"] = {"enabled": False, "prefix": "dis"}

    # Attempt registration; decorator should return early and not add to registry
    mod.register_provider("disabled")(DisabledProvider)
    assert "disabled" not in mod.PROVIDER_REGISTRY


def test_get_primary_provider_name_and_prefixes(
    safe_providers_import, groups_providers
):
    prov = safe_providers_import
    # Set providers mapping for this test
    groups_providers.set_providers(
        {
            "google": {"primary": True, "prefix": "google"},
            "aws": {"prefix": "aws"},
        }
    )
    assert prov.get_primary_provider_name() == "google"
    # Note: `get_provider_prefixes()` was removed from the providers
    # module; only assert the primary provider selection here.


def test_get_primary_provider_name_raises_when_not_configured(
    safe_providers_import, groups_providers
):
    mod = safe_providers_import

    # Case A: providers present but empty dict
    groups_providers.set_providers({})
    with pytest.raises(ValueError):
        mod.get_primary_provider_name()

    # Case B: simulate missing groups entirely
    groups_providers.remove_groups()
    with pytest.raises(ValueError):
        mod.get_primary_provider_name()


def test_get_primary_provider_name_returns_primary(
    safe_providers_import, groups_providers
):
    """When a provider is marked primary in settings, the function should
    return its name. This covers the normal loop/conditional path.
    """
    mod = safe_providers_import
    groups_providers.set_providers(
        {
            "google": {"primary": False, "prefix": "g"},
            "aws": {"primary": True, "prefix": "a"},
            "extra": {"prefix": "x"},
        }
    )

    assert mod.get_primary_provider_name() == "aws"


def test_get_provider_unknown_raises(safe_providers_import):
    """Requesting an unknown provider should raise a ValueError."""
    mod = safe_providers_import
    # ensure registry is empty
    mod.PROVIDER_REGISTRY.clear()
    with pytest.raises(ValueError):
        mod.get_provider("nope")


def test_get_active_providers_filter_and_all(safe_providers_import):
    """get_active_providers should return the whole registry when no filter
    is provided and a single-provider dict when a provider_filter is given.
    """
    mod = safe_providers_import
    mod.PROVIDER_REGISTRY.clear()

    from modules.groups.providers.base import GroupProvider

    class P(GroupProvider):
        def __init__(self):
            pass

        @property
        def capabilities(self):
            return None

        def get_group_members(self, group_key: str, **kwargs):
            raise NotImplementedError()

        def add_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def remove_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def get_user_managed_groups(self, user_key: str):
            raise NotImplementedError()

        def validate_permissions(self, user_key: str, group_key: str, action: str):
            raise NotImplementedError()

        def create_user(self, user_data: dict):
            raise NotImplementedError()

        def delete_user(self, user_key: str):
            raise NotImplementedError()

        def list_groups(self, **kwargs):
            raise NotImplementedError()
        
        def list_groups_with_members(self, **kwargs):
            raise NotImplementedError()

    mod.PROVIDER_REGISTRY["p1"] = P()
    mod.PROVIDER_REGISTRY["p2"] = P()

    all_provs = mod.get_active_providers()
    assert set(all_provs.keys()) == {"p1", "p2"}

    filtered = mod.get_active_providers("p1")
    assert list(filtered.keys()) == ["p1"]


def test_validate_startup_configuration_primary_not_registered(
    safe_providers_import, groups_providers
):
    """If a primary provider is configured but not present in the registry,
    _validate_startup_configuration should raise a RuntimeError.
    """
    mod = safe_providers_import
    # Ensure providers config has a primary entry
    groups_providers.set_providers(
        {"primary": {"primary": True, "prefix": "p", "enabled": True}}
    )

    # Ensure registry does not contain the primary
    mod.PROVIDER_REGISTRY.clear()

    with pytest.raises(RuntimeError):
        mod._validate_startup_configuration()


def test_validate_startup_configuration_requires_role_info(
    safe_providers_import, groups_providers
):
    """Primary provider must advertise provides_role_info=True; otherwise
    startup validation should raise. After toggling the capability to True,
    validation should pass.
    """
    mod = safe_providers_import
    from modules.groups.providers.base import ProviderCapabilities
    from modules.groups.providers.base import GroupProvider

    # Configure primary
    groups_providers.set_providers(
        {"primary": {"primary": True, "prefix": "p", "enabled": True}}
    )

    class Primary(GroupProvider):
        def __init__(self):
            # default capabilities (provides_role_info=False)
            self._capabilities = ProviderCapabilities()

        @property
        def capabilities(self):
            return self._capabilities

        def get_group_members(self, group_key: str, **kwargs):
            raise NotImplementedError()

        def add_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def remove_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def get_user_managed_groups(self, user_key: str):
            raise NotImplementedError()

        def validate_permissions(self, user_key: str, group_key: str, action: str):
            raise NotImplementedError()

        def create_user(self, user_data: dict):
            raise NotImplementedError()

        def delete_user(self, user_key: str):
            raise NotImplementedError()

        def list_groups(self, **kwargs):
            raise NotImplementedError()

        def list_groups_with_members(self, **kwargs):
            raise NotImplementedError()

    # Register primary in the registry without provides_role_info
    mod.PROVIDER_REGISTRY.clear()
    mod.PROVIDER_REGISTRY["primary"] = Primary()

    with pytest.raises(RuntimeError):
        mod._validate_startup_configuration()

    # Now advertise provides_role_info and validation should pass
    mod.PROVIDER_REGISTRY["primary"]._capabilities = ProviderCapabilities(
        provides_role_info=True
    )
    # Should not raise
    mod._validate_startup_configuration()


def test_get_primary_provider_name_and_errors(safe_providers_import, groups_providers):
    mod = safe_providers_import
    # Single primary configured
    groups_providers.set_providers(
        {"a": {"primary": True, "prefix": "p", "enabled": True}}
    )
    assert mod.get_primary_provider_name() == "a"

    # No primary configured -> ValueError
    groups_providers.set_providers({})
    with pytest.raises(ValueError):
        mod.get_primary_provider_name()


def test_validate_startup_configuration_behaviour(
    safe_providers_import, groups_providers
):
    mod = safe_providers_import
    from modules.groups.providers.base import ProviderCapabilities
    from modules.groups.providers.base import GroupProvider

    # When no providers configured, validation is skipped
    groups_providers.set_providers({})
    mod.PROVIDER_REGISTRY.clear()
    # Should not raise
    mod._validate_startup_configuration()

    # Configure a primary but do not register it -> should raise at validation time
    groups_providers.set_providers(
        {"primary": {"primary": True, "prefix": "p", "enabled": True}}
    )
    mod.PROVIDER_REGISTRY.clear()
    with pytest.raises(RuntimeError):
        mod._validate_startup_configuration()

    # Register primary but without provides_role_info -> should raise
    class P(GroupProvider):
        def __init__(self):
            # default capabilities (False)
            self._capabilities = ProviderCapabilities()

        @property
        def capabilities(self):
            return self._capabilities

        def get_group_members(self, group_key: str, **kwargs):
            raise NotImplementedError()

        def add_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def remove_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def get_user_managed_groups(self, user_key: str):
            raise NotImplementedError()

        def validate_permissions(self, user_key: str, group_key: str, action: str):
            raise NotImplementedError()

        def create_user(self, user_data: dict):
            raise NotImplementedError()

        def delete_user(self, user_key: str):
            raise NotImplementedError()

        def list_groups(self):
            raise NotImplementedError()

        def list_groups_with_members(self, **kwargs):
            raise NotImplementedError()

    mod.PROVIDER_REGISTRY["primary"] = P()
    with pytest.raises(RuntimeError):
        mod._validate_startup_configuration()

    # Now advertise provides_role_info and validation should pass
    mod.PROVIDER_REGISTRY["primary"]._capabilities = ProviderCapabilities(
        provides_role_info=True
    )
    # Should not raise
    mod._validate_startup_configuration()
