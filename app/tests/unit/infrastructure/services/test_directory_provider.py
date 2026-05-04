"""Unit tests for get_directory_provider singleton provider."""

from unittest.mock import MagicMock

import pytest

from infrastructure.services import providers


@pytest.fixture(autouse=True)
def clear_directory_provider_cache():
    """Ensure singleton cache is isolated per test."""
    providers.get_directory_provider.cache_clear()
    yield
    providers.get_directory_provider.cache_clear()


def test_get_directory_provider_returns_google_provider_when_configured(monkeypatch):
    """Returns a provider built from the Google builder when provider=google."""
    # Arrange
    mock_directory_settings = MagicMock()
    mock_directory_settings.provider = "google"
    mock_google_clients = MagicMock()
    built_provider = MagicMock()

    monkeypatch.setattr(
        providers,
        "get_directory_settings",
        MagicMock(return_value=mock_directory_settings),
    )
    monkeypatch.setattr(
        providers,
        "get_google_workspace_clients",
        MagicMock(return_value=mock_google_clients),
    )
    monkeypatch.setattr(
        providers,
        "build_google_directory_provider",
        MagicMock(return_value=built_provider),
    )

    # Act
    result = providers.get_directory_provider()

    # Assert
    assert result is built_provider
    providers.build_google_directory_provider.assert_called_once_with(
        google_clients=mock_google_clients,
        directory_settings=mock_directory_settings,
    )


def test_get_directory_provider_raises_for_unsupported_provider(monkeypatch):
    """Raises ValueError for unknown provider keys."""
    # Arrange
    mock_directory_settings = MagicMock()
    mock_directory_settings.provider = "unsupported_idp"

    monkeypatch.setattr(
        providers,
        "get_directory_settings",
        MagicMock(return_value=mock_directory_settings),
    )

    # Act / Assert
    with pytest.raises(ValueError, match="unsupported_idp"):
        providers.get_directory_provider()


def test_get_directory_provider_returns_cached_instance(monkeypatch):
    """Provider accessor returns same instance across repeated calls."""
    # Arrange
    mock_directory_settings = MagicMock()
    mock_directory_settings.provider = "google"
    mock_google_clients = MagicMock()
    built_provider = MagicMock()

    monkeypatch.setattr(
        providers,
        "get_directory_settings",
        MagicMock(return_value=mock_directory_settings),
    )
    monkeypatch.setattr(
        providers,
        "get_google_workspace_clients",
        MagicMock(return_value=mock_google_clients),
    )
    build_spy = MagicMock(return_value=built_provider)
    monkeypatch.setattr(providers, "build_google_directory_provider", build_spy)

    # Act
    instance_one = providers.get_directory_provider()
    instance_two = providers.get_directory_provider()

    # Assert
    assert instance_one is built_provider
    assert instance_two is built_provider
    build_spy.assert_called_once()


def test_get_directory_provider_cache_can_be_cleared(monkeypatch):
    """Cache clear forces a fresh factory build."""
    # Arrange
    mock_directory_settings = MagicMock()
    mock_directory_settings.provider = "google"
    mock_google_clients = MagicMock()
    first_provider = MagicMock()
    second_provider = MagicMock()

    monkeypatch.setattr(
        providers,
        "get_directory_settings",
        MagicMock(return_value=mock_directory_settings),
    )
    monkeypatch.setattr(
        providers,
        "get_google_workspace_clients",
        MagicMock(return_value=mock_google_clients),
    )
    build_spy = MagicMock(side_effect=[first_provider, second_provider])
    monkeypatch.setattr(providers, "build_google_directory_provider", build_spy)

    # Act
    instance_one = providers.get_directory_provider()
    providers.get_directory_provider.cache_clear()
    instance_two = providers.get_directory_provider()

    # Assert
    assert instance_one is first_provider
    assert instance_two is second_provider
    assert build_spy.call_count == 2
