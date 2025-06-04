from unittest.mock import patch
from integrations.google_workspace import sheets


@patch("integrations.google_workspace.sheets.execute_google_api_call")
def test_get_values(mock_execute_google_api_call):

    spreadsheet_id = "1"
    range = "A1:B2"
    fields = "fields"

    sheets.get_values(spreadsheet_id, range, fields)

    mock_execute_google_api_call.assert_called_once_with(
        "sheets",
        "v4",
        "spreadsheets.values",
        "get",
        scopes=['https://www.googleapis.com/auth/spreadsheets'],
        spreadsheetId=spreadsheet_id,
        range=range,
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
        scopes=['https://www.googleapis.com/auth/spreadsheets'],
        spreadsheetId=spreadsheet_id,
        range=None,
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
        scopes=['https://www.googleapis.com/auth/spreadsheets'],
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
        scopes=['https://www.googleapis.com/auth/spreadsheets'],
        spreadsheetId=spreadsheet_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": range, "values": values}],
        },
    )


@patch("integrations.google_workspace.sheets.execute_google_api_call")
def test_append_values(mock_execute_google_api_call):

    spreadsheet_id = "1"
    range = "A1:B2"
    body = {"values": [["a", "b"], ["c", "d"]]}

    sheets.append_values(spreadsheet_id, range, body)

    mock_execute_google_api_call.assert_called_once_with(
        "sheets",
        "v4",
        "spreadsheets.values",
        "append",
        scopes=['https://www.googleapis.com/auth/spreadsheets'],
        spreadsheetId=spreadsheet_id,
        range=range,
        body=body,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
    )
