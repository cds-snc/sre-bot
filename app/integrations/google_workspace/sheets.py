"""Google Sheets API calls."""

from integrations.google_workspace.google_service import (
    handle_google_api_errors,
    execute_google_api_call,
)


@handle_google_api_errors
def get_values(
    spreadsheetId: str, range: str | None = None, includeGridData=None, fields=None
):
    """Gets the values from a Google Sheet.

    Args:
        spreadsheetId (str): The id of the Google Sheet.
        range (str, optional): The range of the values to retrieve.
        includeGridData (bool, optional): Whether to include grid data.
        fields (str, optional): The fields to include in the response.

    Returns:
        dict: The response from the Google Sheets API.
    """
    return execute_google_api_call(
        "sheets",
        "v4",
        "spreadsheets.values",
        "get",
        spreadsheetId=spreadsheetId,
        range=range,
        includeGridData=includeGridData,
        fields=fields,
    )


def batch_update_values(
    spreadsheetId: str,
    range: str,
    values: list,
    valueInputOption: str = "USER_ENTERED",
) -> dict:
    """Updates values in a Google Sheet.

    Args:
        spreadsheetId (str): The id of the Google Sheet.
        range (str): The range to update.
        values (list): The values to update.
        valueInputOption (str, optional): The value input option.

    Returns:
        dict: The response from the Google Sheets API.
    """
    return execute_google_api_call(
        "sheets",
        "v4",
        "spreadsheets.values",
        "batchUpdate",
        spreadsheetId=spreadsheetId,
        body={
            "valueInputOption": valueInputOption,
            "data": [{"range": range, "values": values}],
        },
    )
