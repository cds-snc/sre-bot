"""Unit tests for access sync providers wiring."""

import pytest

from packages.access.common.config import AccessRuntimeConfig as AccessSyncRuntimeConfig
from packages.access.sync import providers
from packages.access.sync.adapters.aws_identity_center import AwsIdentityCenterAdapter
from packages.access.sync.adapters.fake_platform import FakePlatformAdapter


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
def test_get_access_sync_adapters_raises_for_unknown_adapter_type(
    make_platform_policy,
    monkeypatch: pytest.MonkeyPatch,
):
    """Unknown adapter_type values should fail startup-time adapter assembly."""
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

    with pytest.raises(ValueError, match="unknown adapter_type"):
        providers.get_access_sync_adapters()

    providers.get_access_sync_adapters.cache_clear()
