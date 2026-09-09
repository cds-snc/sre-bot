"""Settings contract for the shared SpreadsheetProvider capability."""

from infrastructure.spreadsheets.settings import SpreadsheetSettings, get_spreadsheet_settings


def test_spreadsheet_settings_defaults_to_google() -> None:
    settings = SpreadsheetSettings(_env_file=None)

    assert settings.provider == "google"


def test_spreadsheet_settings_reads_provider_alias(monkeypatch) -> None:
    monkeypatch.setenv("SPREADSHEET_PROVIDER", "google")

    assert SpreadsheetSettings().provider == "google"


def test_get_spreadsheet_settings_is_cached() -> None:
    get_spreadsheet_settings.cache_clear()

    assert get_spreadsheet_settings() is get_spreadsheet_settings()
