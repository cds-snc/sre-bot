"""Unit tests for access sync providers wiring."""

import pytest

from packages.access.sync import providers
from packages.access.sync.adapters.aws_identity_center import AwsIdentityCenterAdapter
from packages.access.sync.adapters.fake_platform import FakePlatformAdapter
from packages.access.common.config import AccessRuntimeConfig as AccessSyncRuntimeConfig


@pytest.mark.unit
def test_get_access_sync_adapters_registers_aws_and_fake(
    make_platform_policy,
    monkeypatch: pytest.MonkeyPatch,
):
    """Adapter wiring includes both aws and fake adapters when configured."""
    # Arrange
    providers.get_access_sync_adapters.cache_clear()
    runtime_config = AccessSyncRuntimeConfig(
        dir_prefix="sg",
        platforms={
            "aws": make_platform_policy(adapter_type="aws_identity_center"),
            "fake": make_platform_policy(adapter_type="fake"),
        },
    )
    monkeypatch.setattr(
        providers,
        "get_access_runtime_config",
        lambda: runtime_config,
    )

    # Act
    adapters = providers.get_access_sync_adapters()

    # Assert
    assert sorted(adapters.keys()) == ["aws", "fake"]
    assert isinstance(adapters["aws"], AwsIdentityCenterAdapter)
    assert isinstance(adapters["fake"], FakePlatformAdapter)

    providers.get_access_sync_adapters.cache_clear()


@pytest.mark.unit
def test_get_access_sync_adapters_ignores_unknown_platforms(
    make_platform_policy,
    monkeypatch: pytest.MonkeyPatch,
):
    """Unsupported platform policy keys should not register an adapter."""
    # Arrange
    providers.get_access_sync_adapters.cache_clear()
    runtime_config = AccessSyncRuntimeConfig(
        dir_prefix="sg",
        platforms={
            "fake": make_platform_policy(adapter_type="fake"),
            "custom": make_platform_policy(adapter_type="custom_unsupported"),
        },
    )
    monkeypatch.setattr(
        providers,
        "get_access_runtime_config",
        lambda: runtime_config,
    )

    # Act
    adapters = providers.get_access_sync_adapters()

    # Assert
    assert sorted(adapters.keys()) == ["fake"]

    providers.get_access_sync_adapters.cache_clear()
