"""Factory for the configured SpreadsheetProvider singleton."""

from collections.abc import Callable
from functools import cache
from typing import TYPE_CHECKING

from infrastructure.spreadsheets.google import GoogleSpreadsheetProvider
from infrastructure.spreadsheets.provider import SpreadsheetProvider
from infrastructure.spreadsheets.settings import SpreadsheetSettings, get_spreadsheet_settings
from integrations.google_workspace.client import get_sheets_service

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource  # pyright: ignore[reportMissingModuleSource]


def build_google_spreadsheet_provider(
    *,
    get_service: Callable[[list[str], str | None], SheetsResource],
    spreadsheet_settings: SpreadsheetSettings,
) -> SpreadsheetProvider:
    """Build a Google Spreadsheet provider with injected dependencies."""
    return GoogleSpreadsheetProvider(get_service=get_service, spreadsheet_settings=spreadsheet_settings)


@cache
def get_spreadsheet_provider() -> SpreadsheetProvider:
    """Return the singleton configured SpreadsheetProvider."""
    spreadsheet_settings = get_spreadsheet_settings()
    if spreadsheet_settings.provider == "google":
        return build_google_spreadsheet_provider(
            get_service=get_sheets_service,
            spreadsheet_settings=spreadsheet_settings,
        )
    raise ValueError(f"Unsupported spreadsheet provider: {spreadsheet_settings.provider!r}")
