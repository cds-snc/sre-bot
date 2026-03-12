"""Unit tests for the directory provider factory."""

from unittest.mock import MagicMock

import pytest

from infrastructure.directory.factory import (
    build_directory_provider,
    build_google_directory_provider,
)
from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.provider import DirectoryProvider


@pytest.fixture
def make_settings():
    """Factory for Settings mock with a configurable directory.provider value."""

    def _make(provider: str = "google"):
        settings = MagicMock()
        settings.directory.provider = provider
        return settings

    return _make


@pytest.fixture
def mock_google_clients():
    """Minimal GoogleWorkspaceClients mock."""
    clients = MagicMock()
    clients.directory = MagicMock()
    return clients


class TestBuildDirectoryProvider:
    def test_returns_google_provider_when_provider_is_google(
        self, make_settings, mock_google_clients
    ):
        # Arrange
        settings = make_settings(provider="google")

        # Act
        provider = build_directory_provider(
            settings=settings, google_clients=mock_google_clients
        )

        # Assert
        assert isinstance(provider, GoogleDirectoryProvider)

    def test_raises_for_unsupported_provider(self, make_settings, mock_google_clients):
        # Arrange
        settings = make_settings(provider="unsupported_idp")

        # Act / Assert
        with pytest.raises(ValueError, match="unsupported_idp"):
            build_directory_provider(
                settings=settings, google_clients=mock_google_clients
            )

    def test_raises_for_entra_id_not_yet_implemented(
        self, make_settings, mock_google_clients
    ):
        # Arrange
        settings = make_settings(provider="entra_id")

        # Act / Assert
        with pytest.raises(ValueError, match="entra_id"):
            build_directory_provider(
                settings=settings, google_clients=mock_google_clients
            )

    def test_returned_object_satisfies_directory_provider_protocol(
        self, make_settings, mock_google_clients
    ):
        # Arrange
        settings = make_settings(provider="google")

        # Act
        provider = build_directory_provider(
            settings=settings, google_clients=mock_google_clients
        )

        # Assert
        assert isinstance(provider, DirectoryProvider)


class TestBuildGoogleDirectoryProvider:
    def test_returns_google_directory_provider_instance(self, mock_google_clients):
        # Act
        provider = build_google_directory_provider(google_clients=mock_google_clients)

        # Assert
        assert isinstance(provider, GoogleDirectoryProvider)

    def test_provider_uses_injected_clients_directory(self, mock_google_clients):
        # Act
        provider = build_google_directory_provider(google_clients=mock_google_clients)

        # Assert — internal _directory attribute is the mocked directory client
        assert provider._directory is mock_google_clients.directory
