"""Factory contract for the SpreadsheetProvider singleton and construction."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from infrastructure.spreadsheets import factory as spreadsheet_factory
from infrastructure.spreadsheets.factory import build_google_spreadsheet_provider
from infrastructure.spreadsheets.google import GoogleSpreadsheetProvider
from infrastructure.spreadsheets.provider import SpreadsheetProvider


def test_build_google_spreadsheet_provider_returns_google_implementation() -> None:
    provider = build_google_spreadsheet_provider(
        get_service=MagicMock(),
        spreadsheet_settings=MagicMock(),
    )

    assert isinstance(provider, GoogleSpreadsheetProvider)
    assert isinstance(provider, SpreadsheetProvider)


def test_build_google_spreadsheet_provider_preserves_injected_dependencies() -> None:
    get_service = MagicMock()
    spreadsheet_settings = MagicMock()

    provider = build_google_spreadsheet_provider(
        get_service=get_service,
        spreadsheet_settings=spreadsheet_settings,
    )

    assert provider._get_service is get_service
    assert provider._spreadsheet_settings is spreadsheet_settings


def test_get_spreadsheet_provider_is_cached_and_uses_sheets_service(monkeypatch) -> None:
    spreadsheet_factory.get_spreadsheet_provider.cache_clear()
    settings = SimpleNamespace(provider="google")
    captured: dict[str, object] = {}

    def fake_builder(*, get_service, spreadsheet_settings):
        captured["get_service"] = get_service
        captured["spreadsheet_settings"] = spreadsheet_settings
        return MagicMock(spec=SpreadsheetProvider)

    observed_service_calls: list[tuple[list[str], str | None]] = []

    def fake_get_sheets_service(scopes, delegated_user_email=None):
        observed_service_calls.append((scopes, delegated_user_email))
        return MagicMock()

    monkeypatch.setattr(spreadsheet_factory, "get_spreadsheet_settings", lambda: settings)
    monkeypatch.setattr(spreadsheet_factory, "get_sheets_service", fake_get_sheets_service)
    monkeypatch.setattr(spreadsheet_factory, "build_google_spreadsheet_provider", fake_builder)

    first = spreadsheet_factory.get_spreadsheet_provider()
    second = spreadsheet_factory.get_spreadsheet_provider()

    assert first is second
    assert captured["spreadsheet_settings"] is settings
    scoped_get_service = captured["get_service"]
    assert callable(scoped_get_service)

    scoped_get_service(["https://www.googleapis.com/auth/spreadsheets"], "caller@example.com")
    assert observed_service_calls == [
        (["https://www.googleapis.com/auth/spreadsheets"], "caller@example.com"),
    ]


def test_get_spreadsheet_provider_rejects_unsupported_provider(monkeypatch) -> None:
    spreadsheet_factory.get_spreadsheet_provider.cache_clear()
    monkeypatch.setattr(spreadsheet_factory, "get_spreadsheet_settings", lambda: SimpleNamespace(provider="excel"))

    with pytest.raises(ValueError, match="Unsupported spreadsheet provider"):
        spreadsheet_factory.get_spreadsheet_provider()
