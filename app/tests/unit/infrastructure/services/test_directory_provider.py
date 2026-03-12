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


def test_get_directory_provider_returns_cached_instance(monkeypatch):
    """Provider accessor returns same instance across repeated calls."""
    # Arrange
    mock_settings = MagicMock()
    mock_google_clients = MagicMock()
    built_provider = MagicMock()

    get_settings_spy = MagicMock(return_value=mock_settings)
    get_google_clients_spy = MagicMock(return_value=mock_google_clients)
    build_provider_spy = MagicMock(return_value=built_provider)

    monkeypatch.setattr(providers, "get_settings", get_settings_spy)
    monkeypatch.setattr(
        providers, "get_google_workspace_clients", get_google_clients_spy
    )
    monkeypatch.setattr(providers, "build_directory_provider", build_provider_spy)

    # Act
    instance_one = providers.get_directory_provider()
    instance_two = providers.get_directory_provider()

    # Assert
    assert instance_one is built_provider
    assert instance_two is built_provider
    get_settings_spy.assert_called_once_with()
    get_google_clients_spy.assert_called_once_with()
    build_provider_spy.assert_called_once_with(
        settings=mock_settings,
        google_clients=mock_google_clients,
    )


def test_get_directory_provider_cache_can_be_cleared(monkeypatch):
    """Cache clear forces a fresh factory build."""
    # Arrange
    mock_settings = MagicMock()
    mock_google_clients = MagicMock()
    first_provider = MagicMock()
    second_provider = MagicMock()

    monkeypatch.setattr(
        providers, "get_settings", MagicMock(return_value=mock_settings)
    )
    monkeypatch.setattr(
        providers,
        "get_google_workspace_clients",
        MagicMock(return_value=mock_google_clients),
    )
    build_provider_spy = MagicMock(side_effect=[first_provider, second_provider])
    monkeypatch.setattr(providers, "build_directory_provider", build_provider_spy)

    # Act
    instance_one = providers.get_directory_provider()
    providers.get_directory_provider.cache_clear()
    instance_two = providers.get_directory_provider()

    # Assert
    assert instance_one is first_provider
    assert instance_two is second_provider
    assert build_provider_spy.call_count == 2
