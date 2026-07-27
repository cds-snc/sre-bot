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


@pytest.mark.unit
def test_get_access_sync_lock_store_is_singleton(monkeypatch: pytest.MonkeyPatch):
    """Lock store provider should cache one store instance for the process."""
    get_lock_store = getattr(providers, "get_access_sync_lock_store", None)
    assert callable(get_lock_store), "packages.access.sync.providers.get_access_sync_lock_store must exist"

    cache_clear = getattr(get_lock_store, "cache_clear", None)
    assert callable(cache_clear)
    cache_clear()

    class _Settings:
        lock_stale_seconds = 14400

    built: list[object] = [object(), object()]

    monkeypatch.setattr(providers, "get_access_sync_settings", lambda: _Settings())
    monkeypatch.setattr(
        "packages.access.sync.providers.build_idempotency_store",
        lambda in_progress_ttl_seconds: built.pop(0),
    )

    first = get_lock_store()
    second = get_lock_store()

    assert first is second
    cache_clear()


@pytest.mark.unit
def test_get_access_sync_lock_store_uses_lock_stale_seconds(monkeypatch: pytest.MonkeyPatch):
    """Lock store TTL must come from access sync lock staleness configuration."""
    get_lock_store = getattr(providers, "get_access_sync_lock_store", None)
    assert callable(get_lock_store), "packages.access.sync.providers.get_access_sync_lock_store must exist"

    cache_clear = getattr(get_lock_store, "cache_clear", None)
    assert callable(cache_clear)
    cache_clear()

    class _Settings:
        lock_stale_seconds = 222

    observed: list[int] = []
    sentinel = object()

    monkeypatch.setattr(providers, "get_access_sync_settings", lambda: _Settings())
    monkeypatch.setattr(
        "packages.access.sync.providers.build_idempotency_store",
        lambda in_progress_ttl_seconds: observed.append(in_progress_ttl_seconds) or sentinel,
    )

    store = get_lock_store()

    assert store is sentinel
    assert observed == [222]
    cache_clear()
