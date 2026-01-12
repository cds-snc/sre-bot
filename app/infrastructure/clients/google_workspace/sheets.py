"""Sheets client for Google Workspace operations.

Provides type-safe access to Google Sheets API (spreadsheets, values, formatting).
All methods return OperationResult for consistent error handling.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

import structlog

from infrastructure.clients.google_workspace.executor import execute_google_api_call
from infrastructure.operations.result import OperationResult

if TYPE_CHECKING:
    from infrastructure.clients.google_workspace.session_provider import (
        SessionProvider,
    )

logger = structlog.get_logger()

# Sheets API scopes
SHEETS_FULL_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"

# Value input options
VALUE_INPUT_OPTION_RAW = "RAW"
VALUE_INPUT_OPTION_USER_ENTERED = "USER_ENTERED"

# Insert data options
INSERT_DATA_OPTION_OVERWRITE = "OVERWRITE"
INSERT_DATA_OPTION_INSERT_ROWS = "INSERT_ROWS"


class SheetsClient:
    """Client for Google Sheets API operations.

    Handles spreadsheet operations, value read/write, and formatting.
    Thread safety: Not thread-safe. Create one instance per thread.

    Args:
        session_provider: SessionProvider for authentication and service creation

    Usage:
        # Get spreadsheet values
        result = sheets_client.get_values(
            spreadsheet_id="abc123",
            cell_range="Sheet1!A1:B10"
        )
        if result.is_success:
            values = result.data["values"]

        # Update values
        result = sheets_client.update_values(
            spreadsheet_id="abc123",
            cell_range="Sheet1!A1:B10",
            values=[["Name", "Email"], ["John", "john@example.com"]]
        )
    """

    def __init__(self, session_provider: "SessionProvider") -> None:
        """Initialize Sheets client.

        Args:
            session_provider: SessionProvider instance for API authentication
        """
        self._session_provider = session_provider
        self._logger = logger.bind(client="sheets")

    # ========================================================================
    # Spreadsheet Operations
    # ========================================================================

    def get_spreadsheet(
        self,
        spreadsheet_id: str,
        ranges: Optional[List[str]] = None,
        include_grid_data: bool = False,
        fields: Optional[str] = None,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Get spreadsheet metadata and optionally data.

        Args:
            spreadsheet_id: The spreadsheet ID
            ranges: Optional list of A1 notation ranges to retrieve
            include_grid_data: Whether to include cell data (default: False)
            fields: Optional field mask to limit returned fields
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with spreadsheet resource

        Reference:
            https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/get
        """
        self._logger.debug(
            "getting_spreadsheet",
            spreadsheet_id=spreadsheet_id,
            include_grid_data=include_grid_data,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="sheets",
            version="v4",
            scopes=[SHEETS_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            request = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                includeGridData=include_grid_data,
            )
            if ranges:
                request = service.spreadsheets().get(
                    spreadsheetId=spreadsheet_id,
                    ranges=ranges,
                    includeGridData=include_grid_data,
                )
            if fields:
                request.uri += f"&fields={fields}"
            return request.execute()

        return execute_google_api_call(
            operation_name="sheets.spreadsheets.get",
            api_callable=api_call,
        )

    def create_spreadsheet(
        self,
        title: str,
        sheet_titles: Optional[List[str]] = None,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Create a new spreadsheet.

        Args:
            title: The spreadsheet title
            sheet_titles: Optional list of sheet titles to create
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with created spreadsheet resource including spreadsheetId

        Reference:
            https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/create
        """
        self._logger.info(
            "creating_spreadsheet",
            title=title,
            sheet_count=len(sheet_titles) if sheet_titles else 1,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="sheets",
            version="v4",
            scopes=[SHEETS_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        body: Dict[str, Any] = {"properties": {"title": title}}

        if sheet_titles:
            body["sheets"] = [
                {"properties": {"title": sheet_title}} for sheet_title in sheet_titles
            ]

        def api_call() -> Any:
            return (
                service.spreadsheets()
                .create(
                    body=body, fields="spreadsheetId,spreadsheetUrl,sheets.properties"
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="sheets.spreadsheets.create",
            api_callable=api_call,
        )

    def batch_update_spreadsheet(
        self,
        spreadsheet_id: str,
        requests: List[Dict[str, Any]],
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Apply batch updates to a spreadsheet (formatting, sheet operations).

        Args:
            spreadsheet_id: The spreadsheet ID
            requests: List of update request objects
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with batch update response

        Reference:
            https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/batchUpdate
        """
        self._logger.info(
            "batch_updating_spreadsheet",
            spreadsheet_id=spreadsheet_id,
            request_count=len(requests),
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="sheets",
            version="v4",
            scopes=[SHEETS_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.spreadsheets()
                .batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests})
                .execute()
            )

        return execute_google_api_call(
            operation_name="sheets.spreadsheets.batchUpdate",
            api_callable=api_call,
        )

    # ========================================================================
    # Values Operations
    # ========================================================================

    def get_values(
        self,
        spreadsheet_id: str,
        cell_range: str,
        major_dimension: str = "ROWS",
        value_render_option: str = "FORMATTED_VALUE",
        date_time_render_option: str = "SERIAL_NUMBER",
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Get values from a range in a spreadsheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            cell_range: The A1 notation range (e.g., "Sheet1!A1:B10")
            major_dimension: "ROWS" or "COLUMNS" (default: "ROWS")
            value_render_option: How values should be represented
            date_time_render_option: How dates should be represented
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with range and values

        Reference:
            https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/get
        """
        self._logger.debug(
            "getting_values",
            spreadsheet_id=spreadsheet_id,
            cell_range=cell_range,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="sheets",
            version="v4",
            scopes=[SHEETS_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=spreadsheet_id,
                    range=cell_range,
                    majorDimension=major_dimension,
                    valueRenderOption=value_render_option,
                    dateTimeRenderOption=date_time_render_option,
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="sheets.values.get",
            api_callable=api_call,
        )

    def update_values(
        self,
        spreadsheet_id: str,
        cell_range: str,
        values: List[List[Any]],
        value_input_option: str = VALUE_INPUT_OPTION_USER_ENTERED,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Update values in a range.

        Args:
            spreadsheet_id: The spreadsheet ID
            cell_range: The A1 notation range (e.g., "Sheet1!A1:B10")
            values: 2D array of values to write
            value_input_option: How input should be interpreted (RAW or USER_ENTERED)
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with update response

        Reference:
            https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/update
        """
        self._logger.info(
            "updating_values",
            spreadsheet_id=spreadsheet_id,
            cell_range=cell_range,
            row_count=len(values),
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="sheets",
            version="v4",
            scopes=[SHEETS_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=spreadsheet_id,
                    range=cell_range,
                    valueInputOption=value_input_option,
                    body={"values": values},
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="sheets.values.update",
            api_callable=api_call,
        )

    def batch_update_values(
        self,
        spreadsheet_id: str,
        data: List[Dict[str, Any]],
        value_input_option: str = VALUE_INPUT_OPTION_USER_ENTERED,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Update multiple ranges in a single request.

        Args:
            spreadsheet_id: The spreadsheet ID
            data: List of range/values dicts [{"range": "A1:B2", "values": [[...]]}]
            value_input_option: How input should be interpreted
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with batch update response

        Reference:
            https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/batchUpdate
        """
        self._logger.info(
            "batch_updating_values",
            spreadsheet_id=spreadsheet_id,
            range_count=len(data),
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="sheets",
            version="v4",
            scopes=[SHEETS_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.spreadsheets()
                .values()
                .batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"valueInputOption": value_input_option, "data": data},
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="sheets.values.batchUpdate",
            api_callable=api_call,
        )

    def append_values(
        self,
        spreadsheet_id: str,
        cell_range: str,
        values: List[List[Any]],
        value_input_option: str = VALUE_INPUT_OPTION_USER_ENTERED,
        insert_data_option: str = INSERT_DATA_OPTION_INSERT_ROWS,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Append values to the end of a range.

        Args:
            spreadsheet_id: The spreadsheet ID
            cell_range: The A1 notation range to append to
            values: 2D array of values to append
            value_input_option: How input should be interpreted
            insert_data_option: How data should be inserted (INSERT_ROWS or OVERWRITE)
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with append response

        Reference:
            https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/append
        """
        self._logger.info(
            "appending_values",
            spreadsheet_id=spreadsheet_id,
            cell_range=cell_range,
            row_count=len(values),
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="sheets",
            version="v4",
            scopes=[SHEETS_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=cell_range,
                    valueInputOption=value_input_option,
                    insertDataOption=insert_data_option,
                    body={"values": values},
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="sheets.values.append",
            api_callable=api_call,
        )

    def clear_values(
        self,
        spreadsheet_id: str,
        cell_range: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Clear values from a range.

        Args:
            spreadsheet_id: The spreadsheet ID
            cell_range: The A1 notation range to clear
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with clear response

        Reference:
            https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/clear
        """
        self._logger.info(
            "clearing_values",
            spreadsheet_id=spreadsheet_id,
            cell_range=cell_range,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="sheets",
            version="v4",
            scopes=[SHEETS_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.spreadsheets()
                .values()
                .clear(spreadsheetId=spreadsheet_id, range=cell_range, body={})
                .execute()
            )

        return execute_google_api_call(
            operation_name="sheets.values.clear",
            api_callable=api_call,
        )
