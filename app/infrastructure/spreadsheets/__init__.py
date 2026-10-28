"""Shared spreadsheet infrastructure capability."""

from infrastructure.spreadsheets.factory import get_spreadsheet_provider
from infrastructure.spreadsheets.google import RANGE_NOT_FOUND
from infrastructure.spreadsheets.models import SheetCell
from infrastructure.spreadsheets.provider import SpreadsheetProvider

__all__ = [
    "RANGE_NOT_FOUND",
    "SheetCell",
    "SpreadsheetProvider",
    "get_spreadsheet_provider",
]
