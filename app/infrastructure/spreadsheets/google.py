"""Google Workspace implementation of the SpreadsheetProvider contract."""

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Literal, cast

from googleapiclient.errors import HttpError

from infrastructure.operations import OperationResult
from infrastructure.operations.status import OperationStatus
from infrastructure.spreadsheets.models import SheetCell
from infrastructure.spreadsheets.settings import SpreadsheetSettings
from integrations.google_workspace.client import classify_google_error

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
RANGE_NOT_FOUND = "RANGE_NOT_FOUND"

_VALUE_INPUT_OPTION = "USER_ENTERED"
_INSERT_DATA_OPTION = "INSERT_ROWS"

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import (  # pyright: ignore[reportMissingModuleSource]
        BatchUpdateValuesRequest,
        SheetsResource,
    )


class GoogleSpreadsheetProvider:
    """SpreadsheetProvider backed by the Google Sheets API."""

    def __init__(
        self,
        get_service: Callable[[list[str], str | None], SheetsResource],
        spreadsheet_settings: SpreadsheetSettings,
    ) -> None:
        self._get_service = get_service
        self._spreadsheet_settings = spreadsheet_settings

    def _map_sdk_exception(self, exc: HttpError, operation: str) -> OperationResult[Any]:
        if int(exc.resp.status) == 400 and "Unable to parse range" in str(exc):
            return OperationResult.error(
                status=OperationStatus.NOT_FOUND,
                message=str(exc),
                error_code=RANGE_NOT_FOUND,
                provider="google",
                operation=operation,
            )

        status, error_code, retry_after = classify_google_error(exc)
        return OperationResult.error(
            status=status,
            message=str(exc),
            error_code=error_code,
            retry_after=retry_after,
            provider="google",
            operation=operation,
        )

    def _call(self, operation: str, fn: Callable[[], Any]) -> OperationResult[Any]:
        try:
            return OperationResult.success(data=fn(), provider="google", operation=operation)
        except HttpError as exc:
            return self._map_sdk_exception(exc, operation)

    def _service(self) -> SheetsResource:
        return self._get_service(SHEETS_SCOPES, None)

    def _success_or_error(self, result: OperationResult[Any], operation: str) -> OperationResult[None]:
        if not result.is_success:
            return OperationResult.error(
                status=result.status,
                message=result.message,
                error_code=result.error_code,
                retry_after=result.retry_after,
                provider=result.provider,
                operation=result.operation,
            )
        return OperationResult.success(provider="google", operation=operation)

    def read_values(self, spreadsheet_id: str, a1_range: str) -> OperationResult[list[list[str]]]:
        """Read a string matrix from an A1 range."""
        result = self._call(
            "read_values",
            lambda: self._service().spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=a1_range).execute(),
        )
        if not result.is_success:
            return cast("OperationResult[list[list[str]]]", result)
        payload = result.data if isinstance(result.data, Mapping) else {}
        raw_values = payload.get("values", [])
        values = raw_values if isinstance(raw_values, list) else []
        return OperationResult.success(
            data=[[str(cell) for cell in row] for row in values if isinstance(row, list)],
            provider="google",
            operation="read_values",
        )

    def update_values(self, spreadsheet_id: str, a1_range: str, values: list[list[Any]]) -> OperationResult[None]:
        """Replace values in an A1 range."""
        result = self._call(
            "update_values",
            lambda: (
                self._service()
                .spreadsheets()
                .values()
                .batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body=cast(
                        "BatchUpdateValuesRequest",
                        {
                            "valueInputOption": cast(
                                "Literal['INPUT_VALUE_OPTION_UNSPECIFIED', 'RAW', 'USER_ENTERED']", _VALUE_INPUT_OPTION
                            ),
                            "data": [{"range": a1_range, "values": values}],
                        },
                    ),
                )
                .execute()
            ),
        )
        return self._success_or_error(result, "update_values")

    def append_values(self, spreadsheet_id: str, a1_range: str, values: list[list[Any]]) -> OperationResult[None]:
        """Append rows to an A1 range using user-entered values."""
        result = self._call(
            "append_values",
            lambda: (
                self._service()
                .spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=a1_range,
                    body={"majorDimension": "ROWS", "values": values},
                    valueInputOption=cast(
                        "Literal['INPUT_VALUE_OPTION_UNSPECIFIED', 'RAW', 'USER_ENTERED']", _VALUE_INPUT_OPTION
                    ),
                    insertDataOption=cast("Literal['OVERWRITE', 'INSERT_ROWS']", _INSERT_DATA_OPTION),
                )
                # Sheets has no idempotency key and a replayed append duplicates rows, so
                # retries stay off until a retries-disabled handle exists at construction.
                .execute(num_retries=0)
            ),
        )
        return self._success_or_error(result, "append_values")

    def read_cells(self, spreadsheet_id: str, a1_range: str) -> OperationResult[list[list[SheetCell]]]:
        """Read canonical cells and links from an A1 range."""
        result = self._call(
            "read_cells",
            lambda: (
                self._service().spreadsheets().get(spreadsheetId=spreadsheet_id, ranges=a1_range, includeGridData=True).execute()
            ),
        )
        if not result.is_success:
            return cast("OperationResult[list[list[SheetCell]]]", result)

        payload = result.data if isinstance(result.data, Mapping) else {}
        sheets = payload.get("sheets", [])
        first_sheet = sheets[0] if isinstance(sheets, list) and sheets else {}
        data = first_sheet.get("data", []) if isinstance(first_sheet, Mapping) else []
        first_data = data[0] if isinstance(data, list) and data else {}
        row_data = first_data.get("rowData", []) if isinstance(first_data, Mapping) else []
        cells = []
        for row in row_data if isinstance(row_data, list) else []:
            raw_cells = row.get("values", []) if isinstance(row, Mapping) else []
            cells.append([self._build_cell(cell) for cell in raw_cells] if isinstance(raw_cells, list) else [])
        return OperationResult.success(data=cells, provider="google", operation="read_cells")

    def _build_cell(self, payload: Mapping[str, Any]) -> SheetCell:
        formatted_value = payload.get("formattedValue")
        link = payload.get("hyperlink")
        return SheetCell(
            formatted_value=str(formatted_value) if formatted_value is not None else None,
            link=str(link) if link is not None else None,
            provider="google",
        )
