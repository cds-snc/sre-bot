"""Provider-agnostic contract for spreadsheet operations."""

from typing import Any, Protocol, runtime_checkable

from infrastructure.operations import OperationResult
from infrastructure.spreadsheets.models import SheetCell


@runtime_checkable
class SpreadsheetProvider(Protocol):
    """Shared operations for reading and writing spreadsheet data."""

    def read_values(self, spreadsheet_id: str, a1_range: str) -> OperationResult[list[list[str]]]:
        """Read formatted values from an A1 range."""
        ...

    def update_values(self, spreadsheet_id: str, a1_range: str, values: list[list[Any]]) -> OperationResult[None]:
        """Replace values in an A1 range."""
        ...

    def append_values(self, spreadsheet_id: str, a1_range: str, values: list[list[Any]]) -> OperationResult[None]:
        """Append rows to an A1 range."""
        ...

    def read_cells(self, spreadsheet_id: str, a1_range: str) -> OperationResult[list[list[SheetCell]]]:
        """Read canonical cells, including optional links, from an A1 range."""
        ...
