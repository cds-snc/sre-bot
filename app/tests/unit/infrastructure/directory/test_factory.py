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
        mock_get_service = MagicMock()

        # Act
        provider = build_google_directory_provider(
            get_service=mock_get_service,
            customer_id="my_customer",
        )

        # Assert
        assert isinstance(provider, GoogleDirectoryProvider)

    def test_returned_object_satisfies_directory_provider_protocol(self):
        # Arrange
        mock_get_service = MagicMock()

        # Act
        provider = build_google_directory_provider(
            get_service=mock_get_service,
            customer_id="my_customer",
        )

        # Assert
        assert isinstance(provider, DirectoryProvider)

    def test_provider_uses_injected_service_factory(self):
        # Arrange
        mock_get_service = MagicMock()

        # Act
        provider = build_google_directory_provider(
            get_service=mock_get_service,
            customer_id="my_customer",
        )

        # Assert — internal attributes reflect the injected scoped service factory
        assert provider._get_service is mock_get_service
        assert provider._customer_id == "my_customer"


@pytest.mark.unit
def test_get_directory_provider_uses_scoped_google_service_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    directory_factory.get_directory_provider.cache_clear()

    workspace_settings = SimpleNamespace(
        tenant=SimpleNamespace(customer_id="C03abc123", delegated_user_email="sre-bot@example.com"),
    )

    captured: dict[str, object] = {}

    def fake_builder(*, get_service, customer_id):
        captured["get_service"] = get_service
        captured["customer_id"] = customer_id
        return MagicMock(spec=DirectoryProvider)

    observed_service_calls: list[tuple[list[str], str | None]] = []

    def fake_get_admin_directory_service(scopes: list[str], delegated_user_email: str | None = None):
        observed_service_calls.append((scopes, delegated_user_email))
        return MagicMock()

    monkeypatch.setattr(directory_factory, "get_google_workspace_settings", lambda: workspace_settings, raising=False)
    monkeypatch.setattr(directory_factory, "get_admin_directory_service", fake_get_admin_directory_service, raising=False)
    monkeypatch.setattr(directory_factory, "build_google_directory_provider", fake_builder)

    provider = directory_factory.get_directory_provider()

    assert isinstance(provider, DirectoryProvider)
    assert captured["customer_id"] == "C03abc123"

    scoped_get_service = captured["get_service"]
    assert callable(scoped_get_service)

    scoped_get_service(["https://www.googleapis.com/auth/admin.directory.user.readonly"])
    assert observed_service_calls == [
        (
            ["https://www.googleapis.com/auth/admin.directory.user.readonly"],
            "sre-bot@example.com",
        )
    ]


@pytest.mark.unit
def test_get_directory_provider_without_a_google_tenant_entry_passes_no_customer_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the Google entry there are no credentials either, so the provider gets no id and no alias."""
    directory_factory.get_directory_provider.cache_clear()
    captured: dict[str, object] = {}

    def fake_builder(*, get_service, customer_id):
        captured["customer_id"] = customer_id
        return MagicMock(spec=DirectoryProvider)

    monkeypatch.setattr(directory_factory, "get_google_workspace_settings", lambda: SimpleNamespace(tenant=None))
    monkeypatch.setattr(directory_factory, "build_google_directory_provider", fake_builder)

    directory_factory.get_directory_provider()
    directory_factory.get_directory_provider.cache_clear()

    assert captured["customer_id"] == ""


def test_the_google_provider_takes_no_settings_argument() -> None:
    """The adapter reads no settings, so neither the builder nor the constructor accepts one."""
    with pytest.raises(TypeError):
        build_google_directory_provider(get_service=MagicMock(), directory_settings=MagicMock(), customer_id="c")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        GoogleDirectoryProvider(get_service=MagicMock(), directory_settings=MagicMock(), customer_id="c")  # type: ignore[call-arg]


def test_the_factory_has_no_provider_dispatch() -> None:
    """The Google provider is built directly: the factory neither reads settings nor names another vendor."""
    assert not hasattr(directory_factory, "get_directory_settings")
