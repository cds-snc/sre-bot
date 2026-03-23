"""Unit tests for Access Sync config module."""

import pytest

from packages.access_sync.config import (
    AccessSyncRuntimeConfig,
    BundleConfigLoader,
    get_access_sync_config_loader,
)


@pytest.mark.unit
def test_bundle_loader_returns_empty_config():
    # Arrange
    loader = BundleConfigLoader()

    # Act
    result = loader.load(ref="default")

    # Assert
    assert result.is_success
    assert isinstance(result.data, AccessSyncRuntimeConfig)
    # Bundle loader returns empty policies — feature is in "waiting mode"
    assert result.data.policies == {}
    assert result.data.entitlement_mode_overrides == []
    assert "waiting mode" in result.message


@pytest.mark.unit
def test_get_access_sync_config_loader_bundle():
    # Arrange / Act
    loader = get_access_sync_config_loader("bundle")

    # Assert
    assert isinstance(loader, BundleConfigLoader)


@pytest.mark.unit
def test_get_access_sync_config_loader_unknown_raises():
    # Act / Assert
    with pytest.raises(NotImplementedError, match="not yet implemented"):
        get_access_sync_config_loader("dynamodb")
