"""Unit tests for access sync providers wiring."""

import pytest

from packages.access.sync import providers
from packages.access.sync.adapters.aws_identity_center import AwsIdentityCenterAdapter
from packages.access.sync.adapters.fake_platform import FakePlatformAdapter
from packages.access.sync.config import AccessSyncRuntimeConfig
from packages.access.sync.policies import PlatformPolicy


def _make_policy() -> PlatformPolicy:
    """Build a minimal platform policy for registry wiring tests."""
    return PlatformPolicy(
        authn_token="authn",
        authn_removal_mode="delete",
    )


@pytest.mark.unit
def test_get_access_sync_adapters_registers_aws_and_fake(
    monkeypatch: pytest.MonkeyPatch,
):
    """Adapter wiring includes both aws and fake adapters when configured."""
    # Arrange
    providers.get_access_sync_adapters.cache_clear()
    runtime_config = AccessSyncRuntimeConfig(
        dir_prefix="sg",
        platforms={
            "aws": _make_policy(),
            "fake": _make_policy(),
        },
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
        dir_prefix="sg",
        platforms={
            "fake": _make_policy(),
            "custom": _make_policy(),
        },
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
