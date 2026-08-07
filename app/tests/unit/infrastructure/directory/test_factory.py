"""Unit tests for the directory provider factory."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from infrastructure.directory import factory as directory_factory
from infrastructure.directory.factory import build_google_directory_provider
from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.provider import DirectoryProvider


class TestBuildGoogleDirectoryProvider:
    def test_returns_google_directory_provider_instance(self):
        # Arrange
        mock_google_clients = MagicMock()
        mock_google_clients.directory = MagicMock()
        mock_directory_settings = MagicMock()

        # Act
        provider = build_google_directory_provider(
            google_clients=mock_google_clients,
            directory_settings=mock_directory_settings,
        )

        # Assert
        assert isinstance(provider, GoogleDirectoryProvider)

    def test_returned_object_satisfies_directory_provider_protocol(self):
        # Arrange
        mock_google_clients = MagicMock()
        mock_google_clients.directory = MagicMock()
        mock_directory_settings = MagicMock()

        # Act
        provider = build_google_directory_provider(
            google_clients=mock_google_clients,
            directory_settings=mock_directory_settings,
        )

        # Assert
        assert isinstance(provider, DirectoryProvider)

    def test_provider_uses_injected_clients_directory(self):
        # Arrange
        mock_google_clients = MagicMock()
        mock_google_clients.directory = MagicMock()
        mock_directory_settings = MagicMock()

        # Act
        provider = build_google_directory_provider(
            google_clients=mock_google_clients,
            directory_settings=mock_directory_settings,
        )

        # Assert — internal _directory attribute is the mocked directory client
        assert provider._directory is mock_google_clients.directory


@pytest.mark.unit
def test_get_directory_provider_uses_scoped_google_service_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    directory_factory.get_directory_provider.cache_clear()

    directory_settings = SimpleNamespace(provider="google")
    workspace_settings = SimpleNamespace(
        SRE_BOT_EMAIL="sre-bot@example.com",
        GOOGLE_WORKSPACE_CUSTOMER_ID="my_customer",
    )

    captured: dict[str, object] = {}

    def fake_builder(*, get_service, directory_settings, customer_id):
        captured["get_service"] = get_service
        captured["directory_settings"] = directory_settings
        captured["customer_id"] = customer_id
        return MagicMock(spec=DirectoryProvider)

    observed_service_calls: list[tuple[list[str], str | None]] = []

    def fake_get_admin_directory_service(scopes: list[str], delegated_user_email: str | None = None):
        observed_service_calls.append((scopes, delegated_user_email))
        return MagicMock()

    monkeypatch.setattr(directory_factory, "get_directory_settings", lambda: directory_settings)
    monkeypatch.setattr(directory_factory, "get_google_workspace_settings", lambda: workspace_settings, raising=False)
    monkeypatch.setattr(directory_factory, "get_admin_directory_service", fake_get_admin_directory_service, raising=False)
    monkeypatch.setattr(directory_factory, "build_google_directory_provider", fake_builder)

    provider = directory_factory.get_directory_provider()

    assert isinstance(provider, DirectoryProvider)
    assert captured["directory_settings"] is directory_settings
    assert captured["customer_id"] == "my_customer"

    scoped_get_service = captured["get_service"]
    assert callable(scoped_get_service)

    scoped_get_service(["https://www.googleapis.com/auth/admin.directory.user.readonly"])
    assert observed_service_calls == [
        (
            ["https://www.googleapis.com/auth/admin.directory.user.readonly"],
            "sre-bot@example.com",
        )
    ]
