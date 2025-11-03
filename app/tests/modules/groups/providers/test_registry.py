# flake8: noqa
"""Test registry behaviors for group providers.

IMPORTANT: NEW CONTRACT after Recommendation 2 (Configuration-Driven Activation)

Provider Activation Contract:
- Discovery Phase: `register_provider()` decorator records classes in DISCOVERED_PROVIDER_CLASSES
- Activation Phase: `activate_providers()` calls settings.groups.providers to filter by enabled field
  - Disabled providers (enabled=False in config) are NEVER instantiated
  - Disabled providers do NOT appear in PROVIDER_REGISTRY after activation
  - Only enabled providers are instantiated and added to PROVIDER_REGISTRY
- Primary Determination: After activation, _determine_primary() selects the primary provider
  - If only one enabled provider exists, it becomes primary
  - If multiple enabled providers exist, exactly one must have is_primary=True in capabilities
  - If only a disabled provider is discovered, ValueError is raised
  - If no enabled providers are discovered, ValueError is raised

Key Rules for Tests:
1. If testing with only one provider, make sure it's enabled (or test expects error)
2. To test disabled behavior, register at least 2 providers with 1+ enabled as primary
3. Use groups_providers fixture to set provider config (enabled/disabled/primary/prefix/capabilities)

Note: this file contains intentionally complex test functions that exercise
many branches of provider activation logic. For lint cleanup during the
migration, disable flake8 checks for this file.
"""

from typing import Optional
import pytest

from modules.groups.providers.base import (
    GroupProvider,
    ProviderCapabilities,
    OperationResult,
    OperationStatus,
)
from modules.groups.models import NormalizedMember


class SuccessProvider(GroupProvider):
    """Provider that returns successful OperationResult for common calls."""

    def __init__(self, provides_role_info: bool = False, is_primary: bool = False):
        self._capabilities = ProviderCapabilities(
            provides_role_info=provides_role_info, is_primary=is_primary
        )

    @property
    def capabilities(self):
        return self._capabilities

    def get_group_members(self, group_key: str, **kwargs) -> OperationResult:
        return OperationResult(status=OperationStatus.SUCCESS, message="ok", data={})

    def add_member(
        self, group_key: str, member_data, justification: str
    ) -> OperationResult:
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def remove_member(
        self, group_key: str, member_data, justification: str
    ) -> OperationResult:
        return OperationResult(status=OperationStatus.SUCCESS, message="ok")

    def list_groups_for_user(
        self, user_key: str, provider_name: Optional[str], **kwargs
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


class NoopProvider(GroupProvider):
    """Provider that raises NotImplementedError for operations."""

    def __init__(self, provides_role_info: bool = False, is_primary: bool = False):
        self._capabilities = ProviderCapabilities(
            provides_role_info=provides_role_info, is_primary=is_primary
        )

    @property
    def capabilities(self):
        return self._capabilities

    def get_group_members(self, group_key: str, **kwargs):
        raise NotImplementedError()

    def add_member(self, group_key: str, member_data, justification: str):
        raise NotImplementedError()

    def remove_member(self, group_key: str, member_data, justification: str):
        raise NotImplementedError()

    def list_groups_for_user(self, user_key: str, *args, **kwargs):
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


class PNoneProvider(GroupProvider):
    """Provider used in tests that expect capabilities to be None."""

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

    def list_groups_for_user(self, user_key: str):
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


def test_register_class_and_instance_and_invalid(
    safe_providers_import, groups_providers
):
    mod = safe_providers_import

    # start with a clean registry
    mod.PROVIDER_REGISTRY.clear()

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

        def list_groups_for_user(
            self, user_key: str, provider_name: Optional[str], **kwargs
        ) -> OperationResult:
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def create_user(self, user_data: NormalizedMember) -> OperationResult:
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

    # Register a class (discovery only)
    mod.PROVIDER_REGISTRY.clear()
    mod.register_provider("dummy")(DummyProvider)

    # Activation must be explicit in the new contract
    mod.activate_providers()
    assert "dummy" in mod.PROVIDER_REGISTRY
    assert isinstance(mod.PROVIDER_REGISTRY["dummy"], GroupProvider)

    # Registering instances via the decorator is no longer supported
    inst = DummyProvider()
    groups_providers.providers["dummy_inst"] = {"enabled": True, "prefix": "di"}
    with pytest.raises(TypeError):
        mod.register_provider("dummy_inst")(inst)

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
    """Provider registration should be skipped when the provider is disabled.

    Tests the NEW contract after Recommendation 2:
    - `register_provider()` decorator records discovery (populates DISCOVERED_PROVIDER_CLASSES)
    - `activate_providers()` reads settings.groups.providers config and filters by `enabled` field
    - Disabled providers (enabled=False) are never instantiated
    - Disabled providers should NOT appear in PROVIDER_REGISTRY after activation
    """
    mod = safe_providers_import
    mod.PROVIDER_REGISTRY.clear()

    class EnabledProvider(GroupProvider):
        """Mock enabled provider to pass primary determination."""

        def __init__(self):
            self._capabilities = ProviderCapabilities(
                provides_role_info=True, is_primary=True
            )

        @property
        def capabilities(self):
            return self._capabilities

        def get_group_members(self, group_key: str, **kwargs):
            raise NotImplementedError()

        def add_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def remove_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def list_groups_for_user(self, user_key: str):
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

    class DisabledProvider(GroupProvider):
        """Mock disabled provider to test skipping."""

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

        def list_groups_for_user(self, user_key: str):
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

    # Configure: one enabled provider (primary) and one disabled provider
    groups_providers.set_providers(
        {
            "enabled": {"enabled": True, "primary": True, "prefix": "ena"},
            "disabled": {"enabled": False, "prefix": "dis"},
        }
    )

    # Discovery phase: register both providers
    mod.register_provider("enabled")(EnabledProvider)
    mod.register_provider("disabled")(DisabledProvider)

    # Discovery does not populate PROVIDER_REGISTRY until activation
    assert "enabled" not in mod.PROVIDER_REGISTRY
    assert "disabled" not in mod.PROVIDER_REGISTRY

    # Activation phase: only enabled providers are instantiated
    mod.activate_providers()

    # After activation: enabled provider IS in registry
    assert "enabled" in mod.PROVIDER_REGISTRY
    # After activation: disabled provider is NOT in registry (contract)
    assert "disabled" not in mod.PROVIDER_REGISTRY


def test_get_primary_provider_name_and_prefixes(
    safe_providers_import, groups_providers
):  # noqa: C901 - test contains many branches; refactor out of scope for lint cleanup
    prov = safe_providers_import
    # Set providers mapping for this test
    groups_providers.set_providers(
        {
            "google": {"primary": True, "prefix": "google"},
            "aws": {"prefix": "aws"},
        }
    )

    class DummyPrimary(GroupProvider):
        def __init__(self):
            # This class represents an explicitly primary provider for the test
            self._capabilities = ProviderCapabilities(
                provides_role_info=True, is_primary=True
            )

        @property
        def capabilities(self):
            return self._capabilities

        def get_group_members(self, group_key: str, **kwargs):
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def add_member(self, group_key: str, member_data, justification: str):
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def remove_member(self, group_key: str, member_data, justification: str):
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def list_groups_for_user(
            self, user_key: str, provider_name: Optional[str], **kwargs
        ):
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def create_user(self, user_data):
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def delete_user(self, user_key: str):
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def list_groups(self, **kwargs):
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def list_groups_with_members(self, **kwargs):
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

    class DummyNonPrimary(GroupProvider):
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

        def list_groups_for_user(self, user_key: str):
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

    # Register google as the primary-capability provider and aws as non-primary
    prov.register_provider("google")(DummyPrimary)
    prov.register_provider("aws")(DummyNonPrimary)
    prov.activate_providers()
    assert prov._PRIMARY_PROVIDER_NAME == "google"
    # Note: `get_provider_prefixes()` was removed from the providers
    # module; only assert the primary provider selection here.


def test_get_primary_provider_name_raises_when_not_configured(
    safe_providers_import, groups_providers
):
    mod = safe_providers_import

    # Case A: providers present but empty dict
    groups_providers.set_providers({})
    # Activation should fail to determine a primary when no discovered
    # providers exist. Clear discovered classes to force failure.
    mod.DISCOVERED_PROVIDER_CLASSES.clear()
    with pytest.raises(ValueError):
        mod.activate_providers()

    # Case B: simulate missing groups entirely
    groups_providers.remove_groups()
    # Ensure no discovered classes so activation cannot pick a primary
    mod.DISCOVERED_PROVIDER_CLASSES.clear()
    with pytest.raises(ValueError):
        mod.activate_providers()


def test_get_primary_provider_name_returns_primary(
    safe_providers_import, groups_providers
):  # noqa: C901 - test contains many branches; refactor out of scope for lint cleanup
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

    class Dummy(GroupProvider):
        def __init__(self):
            self._capabilities = ProviderCapabilities()

        @property
        def capabilities(self):
            return self._capabilities

        def get_group_members(self, group_key: str, **kwargs):
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def add_member(self, group_key: str, member_data, justification: str):
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def remove_member(self, group_key: str, member_data, justification: str):
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def list_groups_for_user(
            self, user_key: str, provider_name: Optional[str], **kwargs
        ):
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def create_user(self, user_data):
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def delete_user(self, user_key: str):
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def list_groups(self, **kwargs):
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def list_groups_with_members(self, **kwargs):
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

    class PrimaryProvider(Dummy):
        @property
        def capabilities(self):
            # Mark this provider as primary via capabilities (new contract)
            return ProviderCapabilities(is_primary=True)

        def get_group_members(self, group_key: str, **kwargs):
            raise NotImplementedError()

        def add_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def remove_member(self, group_key: str, member_data, justification: str):
            raise NotImplementedError()

        def list_groups_for_user(self, user_key: str):
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

    mod.register_provider("google")(Dummy)
    mod.register_provider("aws")(PrimaryProvider)
    mod.register_provider("extra")(Dummy)
    mod.activate_providers()
    assert mod._PRIMARY_PROVIDER_NAME == "aws"


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

        def list_groups_for_user(self, user_key: str):
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
        # pass the configured primary name to the validator
        mod._validate_startup("primary")


def test_validate_startup_configuration_requires_role_info(
    safe_providers_import, groups_providers
):
    """Primary provider must advertise provides_role_info=True; otherwise
    startup validation should raise. After toggling the capability to True,
    validation should pass.
    """
    mod = safe_providers_import

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

        def list_groups_for_user(self, user_key: str):
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
        mod._validate_startup("primary")

    # Now advertise provides_role_info and validation should pass
    mod.PROVIDER_REGISTRY["primary"]._capabilities = ProviderCapabilities(
        provides_role_info=True
    )
    # Should not raise
    # The validator requires a primary to be set during activation; set it here
    mod._PRIMARY_PROVIDER_NAME = "primary"
    mod._validate_startup("primary")


def test_get_primary_provider_name_and_errors(safe_providers_import, groups_providers):
    mod = safe_providers_import
    # Single primary configured
    groups_providers.set_providers(
        {"a": {"primary": True, "prefix": "p", "enabled": True}}
    )

    class A(GroupProvider):
        def __init__(self):
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

        def list_groups_for_user(self, user_key: str):
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

    mod.register_provider("a")(A)
    mod.activate_providers()
    assert mod._PRIMARY_PROVIDER_NAME == "a"

    # No primary configured -> ValueError
    groups_providers.set_providers({})
    # If discovered classes remain activation may still succeed (single discovered
    # provider can become the primary). Clear discovered classes and registry to
    # simulate truly no providers configured/discovered.
    mod.DISCOVERED_PROVIDER_CLASSES.clear()
    mod.PROVIDER_REGISTRY.clear()
    with pytest.raises(ValueError):
        mod.activate_providers()


def test_validate_startup_configuration_behaviour(
    safe_providers_import, groups_providers
):
    mod = safe_providers_import

    # When no providers configured, validation is skipped
    groups_providers.set_providers({})
    mod.PROVIDER_REGISTRY.clear()
    # Should not raise
    # No providers and no primary set: _validate_startup should raise because
    # the new implementation requires a primary to be set during activation.
    with pytest.raises(RuntimeError):
        mod._validate_startup("")

    # Configure a primary but do not register it -> should raise at validation time
    groups_providers.set_providers(
        {"primary": {"primary": True, "prefix": "p", "enabled": True}}
    )
    mod.PROVIDER_REGISTRY.clear()
    with pytest.raises(RuntimeError):
        mod._validate_startup("primary")

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

        def list_groups_for_user(self, user_key: str):
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
        mod._validate_startup("primary")

    # Now advertise provides_role_info and validation should pass
    mod.PROVIDER_REGISTRY["primary"]._capabilities = ProviderCapabilities(
        provides_role_info=True
    )
    # Should not raise
    # To make validation pass, set a primary and advertise provides_role_info
    mod._PRIMARY_PROVIDER_NAME = "primary"
    mod._validate_startup("primary")
