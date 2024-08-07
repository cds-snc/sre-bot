from unittest.mock import patch, MagicMock
from integrations.google_workspace import sheets


@patch("integrations.google_workspace.sheets.execute_google_api_call")
def test_get_values(mock_execute_google_api_call):

    spreadsheet_id = "1"
    range = "A1:B2"
    include_grid_data = True
    fields = "fields"

    sheets.get_values(spreadsheet_id, range, include_grid_data, fields)

    mock_execute_google_api_call.assert_called_once_with(
        "sheets",
        "v4",
        "spreadsheets.values",
        "get",
        spreadsheetId=spreadsheet_id,
        range=range,
        includeGridData=include_grid_data,
        fields=fields,
    )


@patch("integrations.google_workspace.sheets.execute_google_api_call")
def test_get_values_with_defaults(mock_execute_google_api_call):

    spreadsheet_id = "1"

    sheets.get_values(spreadsheet_id)

    mock_execute_google_api_call.assert_called_once_with(
        "sheets",
        "v4",
        "spreadsheets.values",
        "get",
        spreadsheetId=spreadsheet_id,
        range=None,
        includeGridData=None,
        fields=None,
    )


@patch("integrations.google_workspace.sheets.execute_google_api_call")
def test_batch_update_values(mock_execute_google_api_call):

    spreadsheet_id = "1"
    range = "A1:B2"
    values = [["a", "b"], ["c", "d"]]
    value_input_option = "USER_ENTERED"

    sheets.batch_update_values(spreadsheet_id, range, values, value_input_option)

    mock_execute_google_api_call.assert_called_once_with(
        "sheets",
        "v4",
        "spreadsheets.values",
        "batchUpdate",
        spreadsheetId=spreadsheet_id,
        body={
            "valueInputOption": value_input_option,
            "data": [{"range": range, "values": values}],
        },
    )


@patch("integrations.google_workspace.sheets.execute_google_api_call")
def test_batch_update_values_with_defaults(mock_execute_google_api_call):

    spreadsheet_id = "1"
    range = "A1:B2"
    values = [["a", "b"], ["c", "d"]]

    sheets.batch_update_values(spreadsheet_id, range, values)

    mock_execute_google_api_call.assert_called_once_with(
        "sheets",
        "v4",
        "spreadsheets.values",
        "batchUpdate",
        spreadsheetId=spreadsheet_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": range, "values": values}],
        },
    )
