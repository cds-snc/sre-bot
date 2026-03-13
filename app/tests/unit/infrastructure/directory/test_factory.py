"""Unit tests for the directory provider factory."""

from unittest.mock import MagicMock

from infrastructure.directory.factory import build_google_directory_provider
from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.provider import DirectoryProvider


class TestBuildGoogleDirectoryProvider:
    def test_returns_google_directory_provider_instance(self):
        # Arrange
        mock_google_clients = MagicMock()
        mock_google_clients.directory = MagicMock()

        # Act
        provider = build_google_directory_provider(google_clients=mock_google_clients)

        # Assert
        assert isinstance(provider, GoogleDirectoryProvider)

    def test_returned_object_satisfies_directory_provider_protocol(self):
        # Arrange
        mock_google_clients = MagicMock()
        mock_google_clients.directory = MagicMock()

        # Act
        provider = build_google_directory_provider(google_clients=mock_google_clients)

        # Assert
        assert isinstance(provider, DirectoryProvider)

    def test_provider_uses_injected_clients_directory(self):
        # Arrange
        mock_google_clients = MagicMock()
        mock_google_clients.directory = MagicMock()

        # Act
        provider = build_google_directory_provider(google_clients=mock_google_clients)

        # Assert — internal _directory attribute is the mocked directory client
        assert provider._directory is mock_google_clients.directory
