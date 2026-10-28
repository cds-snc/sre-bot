"""Factory contract for the DriveProvider singleton and provider construction."""

from unittest.mock import MagicMock

import pytest

from infrastructure.drive import factory as drive_factory
from infrastructure.drive.factory import build_google_drive_provider
from infrastructure.drive.google import GoogleDriveProvider
from infrastructure.drive.provider import DriveProvider


class TestBuildGoogleDriveProvider:
    def test_returns_google_drive_provider_instance(self):
        provider = build_google_drive_provider(get_service=MagicMock())

        assert isinstance(provider, GoogleDriveProvider)

    def test_returned_object_satisfies_drive_provider_protocol(self):
        provider = build_google_drive_provider(get_service=MagicMock())

        assert isinstance(provider, DriveProvider)

    def test_provider_uses_injected_service_factory(self):
        mock_get_service = MagicMock()

        provider = build_google_drive_provider(get_service=mock_get_service)

        assert provider._get_service is mock_get_service

    def test_builder_and_adapter_take_no_settings_argument(self):
        """The adapter reads no settings, so neither entry point accepts one."""
        with pytest.raises(TypeError):
            build_google_drive_provider(get_service=MagicMock(), drive_settings=MagicMock())  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            GoogleDriveProvider(get_service=MagicMock(), drive_settings=MagicMock())  # type: ignore[call-arg]


@pytest.mark.unit
def test_get_drive_provider_builds_the_google_adapter_with_the_scoped_service_factory(monkeypatch):
    drive_factory.get_drive_provider.cache_clear()
    captured = {}

    def fake_builder(*, get_service):
        captured["get_service"] = get_service
        return MagicMock(spec=DriveProvider)

    observed_service_calls = []

    def fake_get_drive_service(scopes, delegated_user_email=None):
        observed_service_calls.append((scopes, delegated_user_email))
        return MagicMock()

    monkeypatch.setattr(drive_factory, "get_drive_service", fake_get_drive_service, raising=False)
    monkeypatch.setattr(drive_factory, "build_google_drive_provider", fake_builder)

    provider = drive_factory.get_drive_provider()
    drive_factory.get_drive_provider.cache_clear()

    assert isinstance(provider, DriveProvider)
    scoped_get_service = captured["get_service"]
    assert callable(scoped_get_service)

    scoped_get_service(["https://www.googleapis.com/auth/drive"], "caller@example.com")
    assert observed_service_calls == [
        (["https://www.googleapis.com/auth/drive"], "caller@example.com"),
    ]


@pytest.mark.unit
def test_the_drive_settings_module_is_gone():
    """No provider setting exists: the vendor is the Google adapter, never a configured choice."""
    with pytest.raises(ModuleNotFoundError):
        __import__("infrastructure.drive.settings")
