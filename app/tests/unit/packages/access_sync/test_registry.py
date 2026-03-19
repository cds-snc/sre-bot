"""Unit tests for AccessSyncRegistry."""

import pytest

from infrastructure.operations import OperationResult
from packages.access_sync.policies import AdapterCapabilities
from packages.access_sync.registry import AccessSyncRegistry


class MinimalAdapter:
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_disable=False,
            supports_delete=True,
            supported_entitlement_types=set(),
        )

    def ensure_user(self, user_email: str) -> OperationResult:
        return OperationResult.success()


@pytest.mark.unit
def test_registry_get_registered_adapter():
    # Arrange
    adapter = MinimalAdapter()
    registry = AccessSyncRegistry(adapters={"aws": adapter})

    # Act
    result = registry.get_adapter("aws")

    # Assert
    assert result is adapter


@pytest.mark.unit
def test_registry_get_unknown_adapter_raises():
    # Arrange
    registry = AccessSyncRegistry(adapters={})

    # Act / Assert
    with pytest.raises(KeyError):
        registry.get_adapter("gcp")


@pytest.mark.unit
def test_registry_register_adapter():
    # Arrange
    registry = AccessSyncRegistry(adapters={})
    adapter = MinimalAdapter()

    # Act
    registry.register_adapter("aws", adapter)

    # Assert
    assert registry.get_adapter("aws") is adapter


@pytest.mark.unit
def test_registry_registered_platforms_sorted():
    # Arrange
    registry = AccessSyncRegistry(
        adapters={
            "gcp": MinimalAdapter(),
            "aws": MinimalAdapter(),
            "azure": MinimalAdapter(),
        }
    )

    # Act
    platforms = registry.registered_platforms()

    # Assert
    assert platforms == ["aws", "azure", "gcp"]
