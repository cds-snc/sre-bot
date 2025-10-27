"""Minimal provider contract tests.

These tests are intentionally conservative and skipped when the provider
registry or a primary provider is not configured. They exist as a
lightweight contract test that provider implementers can run locally.

Placement: this test lives under `app/tests/` so imports resolve using the
application package root as defined in project conventions.
"""

import inspect
import pytest


def _make_dummy_provider(GroupProvider, ProviderCapabilities):
    """Return a simple provider implementation for tests."""

    class DummyProvider(GroupProvider):
        def __init__(self):
            self._capabilities = ProviderCapabilities(provides_role_info=True)

        @property
        def capabilities(self):
            return self._capabilities

        def get_group_members(self, group_key: str, **kwargs):
            return None

        def add_member(self, group_key: str, member_data, justification: str):
            return None

        def remove_member(self, group_key: str, member_data, justification: str):
            return None

        def get_user_managed_groups(self, user_key: str):
            return None

        def validate_permissions(self, user_key: str, group_key: str, action: str):
            return None

        def create_user(self, user_data: dict):
            return None

        def delete_user(self, user_key: str):
            return None

        def list_groups(self, **kwargs):
            return None

        def list_groups_with_members(self, **kwargs):
            return None

    return DummyProvider


def test_primary_provider_exists_and_has_methods(
    safe_providers_import, groups_providers
):
    """Ensure a primary provider can be registered and exposes public methods.

    This test uses the test fixtures to control import-time behavior and
    inject a small dummy provider as the primary provider so assertions
    below run deterministically.
    """

    mod = safe_providers_import

    # Clear any prior registry state
    mod.PROVIDER_REGISTRY.clear()

    # Prepare settings to declare a primary provider named 'dummy'
    groups_providers.set_providers(
        {"dummy": {"primary": True, "enabled": True, "prefix": "d"}}
    )

    # Resolve base types
    base = pytest.importorskip("modules.groups.providers.base")
    GroupProvider = getattr(base, "GroupProvider")
    ProviderCapabilities = getattr(base, "ProviderCapabilities")

    DummyProvider = _make_dummy_provider(GroupProvider, ProviderCapabilities)

    # Register dummy provider (will read the patched settings)
    mod.register_provider("dummy")(DummyProvider)

    provider = mod.get_provider("dummy")

    assert isinstance(provider, GroupProvider)

    required = ("add_member", "remove_member", "get_group_members", "list_groups")
    for name in required:
        assert hasattr(provider, name), f"Provider missing required method: {name}"
        func = getattr(provider, name)
        assert callable(func), f"Provider method {name} is not callable"


def test_method_signatures_have_expected_params(
    safe_providers_import, groups_providers
):
    """Check that write methods accept a group_key and a member-like param.

    Uses the same dummy provider approach to avoid dependency on global
    configuration during import-time.
    """

    mod = safe_providers_import

    # Ensure a fresh registry and settings
    mod.PROVIDER_REGISTRY.clear()
    groups_providers.set_providers(
        {"dummy": {"primary": True, "enabled": True, "prefix": "d"}}
    )

    base = pytest.importorskip("modules.groups.providers.base")
    GroupProvider = getattr(base, "GroupProvider")
    ProviderCapabilities = getattr(base, "ProviderCapabilities")

    DummyProvider = _make_dummy_provider(GroupProvider, ProviderCapabilities)
    mod.register_provider("dummy")(DummyProvider)

    provider = mod.get_provider("dummy")

    for method_name in ("add_member", "remove_member"):
        func = getattr(provider, method_name)
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # Basic expectation: method should accept a group identifier and a member
        assert any(
            "group" in p for p in params
        ), f"{method_name} should accept a group identifier param; got {params}"
        assert any(
            "member" in p or "member" == p for p in params
        ), f"{method_name} should accept a member param; got {params}"
