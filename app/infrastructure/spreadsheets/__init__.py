"""Shared spreadsheet infrastructure capability."""

from infrastructure.spreadsheets.factory import get_spreadsheet_provider
from infrastructure.spreadsheets.google import RANGE_NOT_FOUND
from infrastructure.spreadsheets.models import SheetCell
from infrastructure.spreadsheets.provider import SpreadsheetProvider
from infrastructure.spreadsheets.settings import SpreadsheetSettings, get_spreadsheet_settings

__all__ = [
    "RANGE_NOT_FOUND",
    "SheetCell",
    "SpreadsheetProvider",
    "SpreadsheetSettings",
    "get_spreadsheet_provider",
    "get_spreadsheet_settings",
]
