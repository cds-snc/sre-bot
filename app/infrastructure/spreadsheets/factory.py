"""Factory for the configured SpreadsheetProvider singleton."""

from collections.abc import Callable
from functools import cache
from typing import TYPE_CHECKING

from infrastructure.spreadsheets.google import GoogleSpreadsheetProvider
from infrastructure.spreadsheets.provider import SpreadsheetProvider
from integrations.google_workspace.client import get_sheets_service

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource  # pyright: ignore[reportMissingModuleSource]


def build_google_spreadsheet_provider(
    *,
    get_service: Callable[[list[str], str | None], SheetsResource],
) -> SpreadsheetProvider:
    """Build a Google Spreadsheet provider with injected dependencies."""
    return GoogleSpreadsheetProvider(get_service=get_service)


@cache
def get_spreadsheet_provider() -> SpreadsheetProvider:
    """Return the singleton SpreadsheetProvider: Google Sheets, the only implementation."""
    return build_google_spreadsheet_provider(get_service=get_sheets_service)
