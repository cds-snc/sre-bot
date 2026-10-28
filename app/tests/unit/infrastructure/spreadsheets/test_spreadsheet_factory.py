"""Factory contract for the SpreadsheetProvider singleton and construction."""

from unittest.mock import MagicMock

import pytest

from infrastructure.spreadsheets import factory as spreadsheet_factory
from infrastructure.spreadsheets.factory import build_google_spreadsheet_provider
from infrastructure.spreadsheets.google import GoogleSpreadsheetProvider
from infrastructure.spreadsheets.provider import SpreadsheetProvider


def test_build_google_spreadsheet_provider_returns_google_implementation() -> None:
    provider = build_google_spreadsheet_provider(get_service=MagicMock())

    assert isinstance(provider, GoogleSpreadsheetProvider)
    assert isinstance(provider, SpreadsheetProvider)


def test_build_google_spreadsheet_provider_preserves_injected_service_factory() -> None:
    get_service = MagicMock()

    provider = build_google_spreadsheet_provider(get_service=get_service)

    assert provider._get_service is get_service


def test_builder_and_adapter_take_no_settings_argument() -> None:
    """The adapter reads no settings, so neither entry point accepts one."""
    with pytest.raises(TypeError):
        build_google_spreadsheet_provider(get_service=MagicMock(), spreadsheet_settings=MagicMock())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        GoogleSpreadsheetProvider(get_service=MagicMock(), spreadsheet_settings=MagicMock())  # type: ignore[call-arg]


def test_get_spreadsheet_provider_is_cached_and_uses_sheets_service(monkeypatch) -> None:
    spreadsheet_factory.get_spreadsheet_provider.cache_clear()
    captured: dict[str, object] = {}

    def fake_builder(*, get_service):
        captured["get_service"] = get_service
        return MagicMock(spec=SpreadsheetProvider)

    observed_service_calls: list[tuple[list[str], str | None]] = []

    def fake_get_sheets_service(scopes, delegated_user_email=None):
        observed_service_calls.append((scopes, delegated_user_email))
        return MagicMock()

    monkeypatch.setattr(spreadsheet_factory, "get_sheets_service", fake_get_sheets_service)
    monkeypatch.setattr(spreadsheet_factory, "build_google_spreadsheet_provider", fake_builder)

    first = spreadsheet_factory.get_spreadsheet_provider()
    second = spreadsheet_factory.get_spreadsheet_provider()
    spreadsheet_factory.get_spreadsheet_provider.cache_clear()

    assert first is second
    scoped_get_service = captured["get_service"]
    assert callable(scoped_get_service)

    scoped_get_service(["https://www.googleapis.com/auth/spreadsheets"], "caller@example.com")
    assert observed_service_calls == [
        (["https://www.googleapis.com/auth/spreadsheets"], "caller@example.com"),
    ]


def test_the_spreadsheet_settings_module_is_gone() -> None:
    """No provider setting exists: the vendor is the Google adapter, never a configured choice."""
    with pytest.raises(ModuleNotFoundError):
        __import__("infrastructure.spreadsheets.settings")
