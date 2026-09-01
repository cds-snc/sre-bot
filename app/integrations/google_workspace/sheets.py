"""Google Sheets API calls."""

from typing import TYPE_CHECKING, Literal, cast

from integrations.google_workspace import client as google_service_client

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import (  # pyright: ignore[reportMissingModuleSource]
        BatchUpdateSpreadsheetRequest,
        BatchUpdateValuesRequest,
        ValueRange,
    )

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_values(spreadsheetId: str, cell_range: str | None = None, fields=None, **kwargs) -> dict:
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
    service = google_service_client.get_sheets_service(
        scopes=SHEETS_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    result: dict = google_service_client.execute_google_api_request(
        service.spreadsheets().values().get(spreadsheetId=spreadsheetId, range=cast("str", cell_range), fields=fields)
    )
    return result


def get_sheet(spreadsheetId: str, ranges: str, includeGridData: bool = False, **kwargs) -> dict:
    """Gets a Google Sheet.

    Args:
        spreadsheetId (str): The id of the Google Sheet.
        ranges (str | None, optional): The ranges to retrieve.
        includeGridData (bool, optional): Whether to include grid data.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The response from the Google Sheets API.
    Reference:
    https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/get
    """
    service = google_service_client.get_sheets_service(
        scopes=SHEETS_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    result: dict = google_service_client.execute_google_api_request(
        service.spreadsheets().get(spreadsheetId=spreadsheetId, ranges=ranges, includeGridData=includeGridData)
    )
    return result


def batch_update(spreadsheetId: str, body: dict, **kwargs) -> dict:
    """Updates a Google Sheet.

    Args:
        spreadsheetId (str): The id of the Google Sheet.
        body (dict): The request body.

    Returns:
        dict: The response from the Google Sheets API.
    """
    service = google_service_client.get_sheets_service(
        scopes=SHEETS_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    body_typed = cast("BatchUpdateSpreadsheetRequest", body)
    result: dict = google_service_client.execute_google_api_request(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheetId, body=body_typed)
    )
    return result


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
    service = google_service_client.get_sheets_service(
        scopes=SHEETS_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    body_typed = cast(
        "BatchUpdateValuesRequest",
        {
            "valueInputOption": valueInputOption,
            "data": [{"range": cell_range, "values": values}],
        },
    )
    result: dict = google_service_client.execute_google_api_request(
        service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheetId, body=body_typed)
    )
    return result


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
    service = google_service_client.get_sheets_service(
        scopes=SHEETS_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    body_typed = cast("ValueRange", body)
    result: dict = google_service_client.execute_google_api_request(
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheetId,
            range=cell_range,
            body=body_typed,
            valueInputOption=cast("Literal['INPUT_VALUE_OPTION_UNSPECIFIED', 'RAW', 'USER_ENTERED']", valueInputOption),
            insertDataOption=cast("Literal['OVERWRITE', 'INSERT_ROWS']", insertDataOption),
        )
    )
    return result
