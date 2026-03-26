"""Unit tests for access sync providers wiring."""

import pytest

from packages.access_sync import providers
from packages.access_sync.adapters.aws_identity_center import AwsIdentityCenterAdapter
from packages.access_sync.adapters.fake_platform import FakePlatformAdapter
from packages.access_sync.config import AccessSyncRuntimeConfig
from packages.access_sync.policies import PlatformPolicy


def _make_policy(platform: str) -> PlatformPolicy:
    """Build a minimal platform policy for registry wiring tests."""
    return PlatformPolicy(
        platform=platform,
        authn_group_slug=f"sg-{platform}-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=[],
    )


@pytest.mark.unit
def test_get_access_sync_adapters_registers_aws_and_fake(
    monkeypatch: pytest.MonkeyPatch,
):
    """Adapter wiring includes both aws and fake adapters when configured."""
    # Arrange
    providers.get_access_sync_adapters.cache_clear()
    runtime_config = AccessSyncRuntimeConfig(
        policies={
            "aws": _make_policy("aws"),
            "fake": _make_policy("fake"),
        }
    )
    monkeypatch.setattr(
        providers,
        "get_access_sync_runtime_config",
        lambda: runtime_config,
    )
    monkeypatch.setattr(providers, "get_aws_clients", lambda: object())

    # Act
    adapters = providers.get_access_sync_adapters()

    # Assert
    assert sorted(adapters.keys()) == ["aws", "fake"]
    assert isinstance(adapters["aws"], AwsIdentityCenterAdapter)
    assert isinstance(adapters["fake"], FakePlatformAdapter)

    providers.get_access_sync_adapters.cache_clear()


@pytest.mark.unit
def test_get_access_sync_adapters_ignores_unknown_platforms(
    monkeypatch: pytest.MonkeyPatch,
):
    """Unsupported platform policy keys should not register an adapter."""
    # Arrange
    providers.get_access_sync_adapters.cache_clear()
    runtime_config = AccessSyncRuntimeConfig(
        policies={
            "fake": _make_policy("fake"),
            "custom": _make_policy("custom"),
        }
    )
    monkeypatch.setattr(
        providers,
        "get_access_sync_runtime_config",
        lambda: runtime_config,
    )

    # Act
    adapters = providers.get_access_sync_adapters()

    # Assert
    assert sorted(adapters.keys()) == ["fake"]

    providers.get_access_sync_adapters.cache_clear()
