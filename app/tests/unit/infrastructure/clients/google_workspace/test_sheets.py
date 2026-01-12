"""Unit tests for SheetsClient."""


import pytest

from infrastructure.clients.google_workspace.sheets import (
    SheetsClient,
)
from infrastructure.operations.result import OperationResult


@pytest.fixture
def mock_service(mock_session_provider):
    """Get the mock Google Sheets service from session provider.

    This is the MagicMock service that supports chaining.
    """
    return mock_session_provider.get_service.return_value


@pytest.fixture
def sheets_client(mock_session_provider):
    """Create SheetsClient with mocked session provider from conftest."""
    return SheetsClient(session_provider=mock_session_provider)


class TestSpreadsheetOperations:
    """Test spreadsheet operations."""

    def test_get_spreadsheet_success(self, sheets_client, mock_service):
        """Test getting spreadsheet metadata."""
        # Arrange
        mock_service.spreadsheets().get().execute.return_value = {
            "spreadsheetId": "sheet123",
            "properties": {"title": "Test Spreadsheet"},
            "sheets": [{"properties": {"title": "Sheet1"}}],
        }

        # Act
        result = sheets_client.get_spreadsheet(spreadsheet_id="sheet123")

        # Assert
        assert result.is_success
        assert result.data["spreadsheetId"] == "sheet123"
        assert result.data["properties"]["title"] == "Test Spreadsheet"

    def test_get_spreadsheet_with_ranges(self, sheets_client, mock_service):
        """Test getting spreadsheet with specific ranges."""
        # Arrange
        mock_service.spreadsheets().get().execute.return_value = {
            "spreadsheetId": "sheet123",
        }

        # Act
        result = sheets_client.get_spreadsheet(
            spreadsheet_id="sheet123", ranges=["Sheet1!A1:B10", "Sheet2!C1:D5"]
        )

        # Assert
        assert result.is_success

    def test_get_spreadsheet_with_grid_data(self, sheets_client, mock_service):
        """Test getting spreadsheet with grid data included."""
        # Arrange
        mock_service.spreadsheets().get().execute.return_value = {
            "spreadsheetId": "sheet123",
            "sheets": [
                {"data": [{"rowData": [{"values": [{"formattedValue": "Test"}]}]}]}
            ],
        }

        # Act
        result = sheets_client.get_spreadsheet(
            spreadsheet_id="sheet123", include_grid_data=True
        )

        # Assert
        assert result.is_success

    def test_create_spreadsheet_success(self, sheets_client, mock_service):
        """Test creating a new spreadsheet."""
        # Arrange
        mock_service.spreadsheets().create().execute.return_value = {
            "spreadsheetId": "new123",
            "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/new123",
        }

        # Act
        result = sheets_client.create_spreadsheet(title="New Spreadsheet")

        # Assert
        assert result.is_success
        assert result.data["spreadsheetId"] == "new123"

    def test_create_spreadsheet_with_multiple_sheets(self, sheets_client, mock_service):
        """Test creating spreadsheet with multiple named sheets."""
        # Arrange
        mock_service.spreadsheets().create().execute.return_value = {
            "spreadsheetId": "new123",
        }

        # Act
        result = sheets_client.create_spreadsheet(
            title="Multi-Sheet",
            sheet_titles=["Data", "Summary", "Archive"],
        )

        # Assert
        assert result.is_success
        # Verify the create call included sheet titles
        call_kwargs = mock_service.spreadsheets().create.call_args[1]
        assert "body" in call_kwargs
        assert "sheets" in call_kwargs["body"]
        assert len(call_kwargs["body"]["sheets"]) == 3

    def test_batch_update_spreadsheet_success(self, sheets_client, mock_service):
        """Test batch updating spreadsheet properties."""
        # Arrange
        mock_service.spreadsheets().batchUpdate().execute.return_value = {
            "spreadsheetId": "sheet123",
            "replies": [{}],
        }

        requests = [
            {
                "updateSpreadsheetProperties": {
                    "properties": {"title": "Updated Title"},
                    "fields": "title",
                }
            }
        ]

        # Act
        result = sheets_client.batch_update_spreadsheet(
            spreadsheet_id="sheet123", requests=requests
        )

        # Assert
        assert result.is_success


class TestValuesOperations:
    """Test value read/write operations."""

    def test_get_values_success(self, sheets_client, mock_service):
        """Test getting values from a range."""
        # Arrange
        mock_service.spreadsheets().values().get().execute.return_value = {
            "range": "Sheet1!A1:B2",
            "majorDimension": "ROWS",
            "values": [["Name", "Email"], ["John", "john@example.com"]],
        }

        # Act
        result = sheets_client.get_values(
            spreadsheet_id="sheet123", cell_range="Sheet1!A1:B2"
        )

        # Assert
        assert result.is_success
        assert len(result.data["values"]) == 2
        assert result.data["values"][0][0] == "Name"

    def test_get_values_empty_range(self, sheets_client, mock_service):
        """Test getting values from empty range."""
        # Arrange
        mock_service.spreadsheets().values().get().execute.return_value = {
            "range": "Sheet1!A1:B2",
            "majorDimension": "ROWS",
        }

        # Act
        result = sheets_client.get_values(
            spreadsheet_id="sheet123", cell_range="Sheet1!A1:B2"
        )

        # Assert
        assert result.is_success
        assert "values" not in result.data

    def test_update_values_success(self, sheets_client, mock_service):
        """Test updating values in a range."""
        # Arrange
        mock_service.spreadsheets().values().update().execute.return_value = {
            "spreadsheetId": "sheet123",
            "updatedRange": "Sheet1!A1:B2",
            "updatedRows": 2,
            "updatedColumns": 2,
            "updatedCells": 4,
        }

        # Act
        result = sheets_client.update_values(
            spreadsheet_id="sheet123",
            cell_range="Sheet1!A1:B2",
            values=[["Name", "Email"], ["Jane", "jane@example.com"]],
        )

        # Assert
        assert result.is_success
        assert result.data["updatedRows"] == 2

    def test_update_values_with_raw_input(self, sheets_client, mock_service):
        """Test updating values with RAW input option."""
        # Arrange
        mock_service.spreadsheets().values().update().execute.return_value = {
            "updatedCells": 1,
        }

        # Act
        result = sheets_client.update_values(
            spreadsheet_id="sheet123",
            cell_range="Sheet1!A1",
            values=[["=SUM(B1:B10)"]],
            value_input_option="RAW",
        )

        # Assert
        assert result.is_success

    def test_batch_update_values_success(self, sheets_client, mock_service):
        """Test updating multiple ranges in one call."""
        # Arrange
        mock_service.spreadsheets().values().batchUpdate().execute.return_value = {
            "spreadsheetId": "sheet123",
            "totalUpdatedRows": 4,
            "totalUpdatedColumns": 2,
            "totalUpdatedCells": 8,
        }

        data = [
            {"range": "Sheet1!A1:B2", "values": [["A", "B"], ["1", "2"]]},
            {"range": "Sheet2!C3:D4", "values": [["C", "D"], ["3", "4"]]},
        ]

        # Act
        result = sheets_client.batch_update_values(spreadsheet_id="sheet123", data=data)

        # Assert
        assert result.is_success
        assert result.data["totalUpdatedCells"] == 8

    def test_append_values_success(self, sheets_client, mock_service):
        """Test appending values to a range."""
        # Arrange
        mock_service.spreadsheets().values().append().execute.return_value = {
            "spreadsheetId": "sheet123",
            "tableRange": "Sheet1!A1:B10",
            "updates": {
                "updatedRange": "Sheet1!A11:B11",
                "updatedRows": 1,
                "updatedColumns": 2,
            },
        }

        # Act
        result = sheets_client.append_values(
            spreadsheet_id="sheet123",
            cell_range="Sheet1!A:B",
            values=[["New", "Row"]],
        )

        # Assert
        assert result.is_success
        assert result.data["updates"]["updatedRows"] == 1

    def test_append_values_with_overwrite(self, sheets_client, mock_service):
        """Test appending values with OVERWRITE option."""
        # Arrange
        mock_service.spreadsheets().values().append().execute.return_value = {
            "updates": {"updatedRows": 1},
        }

        # Act
        result = sheets_client.append_values(
            spreadsheet_id="sheet123",
            cell_range="Sheet1!A:B",
            values=[["Data"]],
            insert_data_option="OVERWRITE",
        )

        # Assert
        assert result.is_success

    def test_clear_values_success(self, sheets_client, mock_service):
        """Test clearing values from a range."""
        # Arrange
        mock_service.spreadsheets().values().clear().execute.return_value = {
            "spreadsheetId": "sheet123",
            "clearedRange": "Sheet1!A1:B10",
        }

        # Act
        result = sheets_client.clear_values(
            spreadsheet_id="sheet123", cell_range="Sheet1!A1:B10"
        )

        # Assert
        assert result.is_success
        assert result.data["clearedRange"] == "Sheet1!A1:B10"


class TestDelegation:
    """Test delegated authentication."""

    def test_get_values_with_delegation(
        self, sheets_client, mock_session_provider, mock_service
    ):
        """Test getting values with delegated authentication."""
        # Arrange
        mock_service.spreadsheets().values().get().execute.return_value = {
            "values": [[]]
        }

        # Act
        result = sheets_client.get_values(
            spreadsheet_id="sheet123",
            cell_range="Sheet1!A1",
            delegated_email="user@example.com",
        )

        # Assert
        assert result.is_success
        # Verify get_service was called with delegated_user_email parameter
        mock_session_provider.get_service.assert_called()
        call_kwargs = mock_session_provider.get_service.call_args.kwargs
        assert "delegated_user_email" in call_kwargs or "delegated_email" in call_kwargs


class TestConstants:
    """Test that constants are properly defined."""

    def test_value_input_options(self):
        """Test value input option constants."""
        from infrastructure.clients.google_workspace.sheets import (
            VALUE_INPUT_OPTION_RAW,
            VALUE_INPUT_OPTION_USER_ENTERED,
        )

        assert VALUE_INPUT_OPTION_RAW == "RAW"
        assert VALUE_INPUT_OPTION_USER_ENTERED == "USER_ENTERED"

    def test_insert_data_options(self):
        """Test insert data option constants."""
        from infrastructure.clients.google_workspace.sheets import (
            INSERT_DATA_OPTION_OVERWRITE,
            INSERT_DATA_OPTION_INSERT_ROWS,
        )

        assert INSERT_DATA_OPTION_OVERWRITE == "OVERWRITE"
        assert INSERT_DATA_OPTION_INSERT_ROWS == "INSERT_ROWS"


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_api_call_propagates_operation_result(self, sheets_client, mock_service):
        """Test that API calls return results wrapped in OperationResult."""
        # Arrange
        mock_service.spreadsheets().get().execute.return_value = {
            "spreadsheetId": "sheet123",
        }

        # Act
        result = sheets_client.get_spreadsheet(spreadsheet_id="sheet123")

        # Assert
        assert isinstance(result, OperationResult)
        assert result.is_success
        assert result.data["spreadsheetId"] == "sheet123"
