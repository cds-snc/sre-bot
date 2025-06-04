"""Google Sheets API calls."""

from integrations.google_workspace.google_service import (
    handle_google_api_errors,
    execute_google_api_call,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@handle_google_api_errors
def get_values(
    spreadsheetId: str, cell_range: str | None = None, fields=None, **kwargs
) -> dict:
    """Gets the values from a Google Sheet.

    Args:
        spreadsheetId (str): The id of the Google Sheet.
        cell_range (str, optional): The range of the values to retrieve.
        includeGridData (bool, optional): Whether to include grid data.
        fields (str, optional): The fields to include in the response.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The response from the Google Sheets API.
    """
    return execute_google_api_call(
        "sheets",
        "v4",
        "spreadsheets.values",
        "get",
        scopes=SCOPES,
        spreadsheetId=spreadsheetId,
        range=cell_range,
        fields=fields,
        **kwargs,
    )


@handle_google_api_errors
def get_sheet(
    spreadsheetId: str, ranges: str, includeGridData: bool = False, **kwargs
) -> dict:
    """Gets a Google Sheet.

    Args:
        spreadsheetId (str): The id of the Google Sheet.
        sheetId (int): The id of the sheet.

    Returns:
        dict: The response from the Google Sheets API.
    Reference:
    https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/get
    """
    return execute_google_api_call(
        "sheets",
        "v4",
        "spreadsheets",
        "get",
        scopes=SCOPES,
        spreadsheetId=spreadsheetId,
        ranges=ranges,
        includeGridData=includeGridData,
        **kwargs,
    )


@handle_google_api_errors
def batch_update(spreadsheetId: str, body: dict, **kwargs) -> dict:
    """Updates a Google Sheet.

    Args:
        spreadsheetId (str): The id of the Google Sheet.
        body (dict): The request body.

    Returns:
        dict: The response from the Google Sheets API.
    """
    return execute_google_api_call(
        "sheets",
        "v4",
        "spreadsheets",
        "batchUpdate",
        scopes=SCOPES,
        spreadsheetId=spreadsheetId,
        body=body,
        **kwargs,
    )


@handle_google_api_errors
def batch_update_values(
    spreadsheetId: str,
    cell_range: str,
    values: list,
    valueInputOption: str = "USER_ENTERED",
    **kwargs,
) -> dict:
    """Updates values in a Google Sheet.

    Args:
        spreadsheetId (str): The id of the Google Sheet.
        cell_range (str): The range to update.
        values (list): The values to update.
        valueInputOption (str, optional): The value input option.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The response from the Google Sheets API.
    """
    return execute_google_api_call(
        "sheets",
        "v4",
        "spreadsheets.values",
        "batchUpdate",
        scopes=SCOPES,
        spreadsheetId=spreadsheetId,
        body={
            "valueInputOption": valueInputOption,
            "data": [{"range": cell_range, "values": values}],
        },
    )


@handle_google_api_errors
def append_values(
    spreadsheetId: str,
    cell_range: str,
    body: dict,
    valueInputOption: str = "USER_ENTERED",
    insertDataOption: str = "INSERT_ROWS",
    **kwargs,
) -> dict:
    """Appends values to a Google Sheet.

    Args:
        spreadsheetId (str): The id of the Google Sheet.
        cell_range (str): The range to append to.
        body (dict): The values to append.

    Returns:
        dict: The response from the Google Sheets API.
    """
    return execute_google_api_call(
        "sheets",
        "v4",
        "spreadsheets.values",
        "append",
        scopes=SCOPES,
        spreadsheetId=spreadsheetId,
        range=cell_range,
        body=body,
        valueInputOption=valueInputOption,
        insertDataOption=insertDataOption,
        **kwargs,
    )
