"""Factory contract for the DriveProvider singleton and provider construction."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from infrastructure.drive import factory as drive_factory
from infrastructure.drive.factory import build_google_drive_provider
from infrastructure.drive.google import GoogleDriveProvider
from infrastructure.drive.provider import DriveProvider


class TestBuildGoogleDriveProvider:
    def test_returns_google_drive_provider_instance(self):
        provider = build_google_drive_provider(
            get_service=MagicMock(),
            drive_settings=MagicMock(),
        )

        assert isinstance(provider, GoogleDriveProvider)

    def test_returned_object_satisfies_drive_provider_protocol(self):
        provider = build_google_drive_provider(
            get_service=MagicMock(),
            drive_settings=MagicMock(),
        )

        assert isinstance(provider, DriveProvider)

    def test_provider_uses_injected_service_factory(self):
        mock_get_service = MagicMock()
        mock_drive_settings = MagicMock()

        provider = build_google_drive_provider(
            get_service=mock_get_service,
            drive_settings=mock_drive_settings,
        )

        assert provider._get_service is mock_get_service
        assert provider._drive_settings is mock_drive_settings


@pytest.mark.unit
def test_get_drive_provider_uses_scoped_google_service_factory(monkeypatch):
    drive_factory.get_drive_provider.cache_clear()

    drive_settings = SimpleNamespace(provider="google")
    workspace_settings = SimpleNamespace(SRE_BOT_EMAIL="sre-bot@example.com")
    captured = {}

    def fake_builder(*, get_service, drive_settings):
        captured["get_service"] = get_service
        captured["drive_settings"] = drive_settings
        return MagicMock(spec=DriveProvider)

    observed_service_calls = []

    def fake_get_drive_service(scopes, delegated_user_email=None):
        observed_service_calls.append((scopes, delegated_user_email))
        return MagicMock()

    monkeypatch.setattr(drive_factory, "get_drive_settings", lambda: drive_settings)
    monkeypatch.setattr(drive_factory, "get_google_workspace_settings", lambda: workspace_settings, raising=False)
    monkeypatch.setattr(drive_factory, "get_drive_service", fake_get_drive_service, raising=False)
    monkeypatch.setattr(drive_factory, "build_google_drive_provider", fake_builder)

    provider = drive_factory.get_drive_provider()

    assert isinstance(provider, DriveProvider)
    assert captured["drive_settings"] is drive_settings

    scoped_get_service = captured["get_service"]
    assert callable(scoped_get_service)

    scoped_get_service(["https://www.googleapis.com/auth/drive"])
    assert observed_service_calls == [
        (["https://www.googleapis.com/auth/drive"], "sre-bot@example.com"),
    ]
