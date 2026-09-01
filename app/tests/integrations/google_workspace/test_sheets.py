"""Unit tests for the sheets module (factory-built, stub-typed Resource path)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from integrations.google_workspace import client as google_client
from integrations.google_workspace import sheets

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _http_error(status: int, reason: str = "boom") -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = reason

    return HttpError(resp=FakeResp(), content=b"{}")


@pytest.fixture
def sheets_client(monkeypatch):
    """Patch the Sheets service factory and expose the mocked stub-typed Resource chain."""
    if not hasattr(google_client, "get_sheets_service"):
        pytest.fail("integrations.google_workspace.client.get_sheets_service is not implemented")

    service = MagicMock()
    factory = MagicMock(return_value=service)
    monkeypatch.setattr(google_client, "get_sheets_service", factory)
    if hasattr(sheets, "get_sheets_service"):
        monkeypatch.setattr(sheets, "get_sheets_service", factory)
    return SimpleNamespace(
        factory=factory,
        service=service,
        spreadsheets=service.spreadsheets.return_value,
        values=service.spreadsheets.return_value.values.return_value,
    )


def test_get_values_returns_result(sheets_client):
    get_call = sheets_client.values.get
    get_call.return_value.execute.return_value = {"range": "A1:B2", "values": [["a", "b"]]}

    result = sheets.get_values("1", "A1:B2", "fields")

    sheets_client.factory.assert_called_once_with(scopes=SHEETS_SCOPES, delegated_user_email=None)
    get_call.assert_called_once_with(spreadsheetId="1", range="A1:B2", fields="fields")
    assert result == {"range": "A1:B2", "values": [["a", "b"]]}


def test_get_values_with_defaults(sheets_client):
    get_call = sheets_client.values.get
    get_call.return_value.execute.return_value = {}

    sheets.get_values("1")

    get_call.assert_called_once_with(spreadsheetId="1", range=None, fields=None)


def test_get_values_passes_delegated_user_email(sheets_client):
    sheets_client.values.get.return_value.execute.return_value = {}

    sheets.get_values("1", delegated_user_email="custom@example.com")

    sheets_client.factory.assert_called_once_with(scopes=SHEETS_SCOPES, delegated_user_email="custom@example.com")


def test_get_values_propagates_http_error(sheets_client):
    error = _http_error(429)
    sheets_client.values.get.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        sheets.get_values("1")

    assert exc_info.value is error


def test_get_sheet_returns_result(sheets_client):
    get_call = sheets_client.spreadsheets.get
    get_call.return_value.execute.return_value = {"spreadsheetId": "1", "sheets": [{}]}

    result = sheets.get_sheet("1", "Sheet1", includeGridData=True)

    sheets_client.factory.assert_called_once_with(scopes=SHEETS_SCOPES, delegated_user_email=None)
    get_call.assert_called_once_with(spreadsheetId="1", ranges="Sheet1", includeGridData=True)
    assert result == {"spreadsheetId": "1", "sheets": [{}]}


def test_get_sheet_with_defaults(sheets_client):
    get_call = sheets_client.spreadsheets.get
    get_call.return_value.execute.return_value = {}

    sheets.get_sheet("1", "Sheet1")

    get_call.assert_called_once_with(spreadsheetId="1", ranges="Sheet1", includeGridData=False)


def test_get_sheet_passes_delegated_user_email(sheets_client):
    sheets_client.spreadsheets.get.return_value.execute.return_value = {}

    sheets.get_sheet("1", "Sheet1", delegated_user_email="custom@example.com")

    sheets_client.factory.assert_called_once_with(scopes=SHEETS_SCOPES, delegated_user_email="custom@example.com")


def test_get_sheet_propagates_http_error(sheets_client):
    error = _http_error(429)
    sheets_client.spreadsheets.get.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        sheets.get_sheet("1", "Sheet1")

    assert exc_info.value is error


def test_get_sheet_no_longer_swallows_unable_to_parse_range(sheets_client):
    """The non-critical 'Unable to parse range' swallow moved to the caller; the client always raises."""
    error = _http_error(400, reason="Unable to parse range: Sheet1")
    sheets_client.spreadsheets.get.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        sheets.get_sheet("1", "Sheet1")

    assert exc_info.value is error


def test_batch_update_returns_result(sheets_client):
    batch_update_call = sheets_client.spreadsheets.batchUpdate
    batch_update_call.return_value.execute.return_value = {"spreadsheetId": "1", "replies": []}
    body = {"requests": [{"updateCells": {}}]}

    result = sheets.batch_update("1", body)

    sheets_client.factory.assert_called_once_with(scopes=SHEETS_SCOPES, delegated_user_email=None)
    batch_update_call.assert_called_once_with(spreadsheetId="1", body=body)
    assert result == {"spreadsheetId": "1", "replies": []}


def test_batch_update_passes_delegated_user_email(sheets_client):
    sheets_client.spreadsheets.batchUpdate.return_value.execute.return_value = {}

    sheets.batch_update("1", {"requests": []}, delegated_user_email="custom@example.com")

    sheets_client.factory.assert_called_once_with(scopes=SHEETS_SCOPES, delegated_user_email="custom@example.com")


def test_batch_update_propagates_http_error(sheets_client):
    error = _http_error(429)
    sheets_client.spreadsheets.batchUpdate.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        sheets.batch_update("1", {"requests": []})

    assert exc_info.value is error


def test_batch_update_values_returns_result(sheets_client):
    batch_update_call = sheets_client.values.batchUpdate
    batch_update_call.return_value.execute.return_value = {"totalUpdatedCells": 4}
    values = [["a", "b"], ["c", "d"]]

    result = sheets.batch_update_values("1", "A1:B2", values, "USER_ENTERED")

    sheets_client.factory.assert_called_once_with(scopes=SHEETS_SCOPES, delegated_user_email=None)
    batch_update_call.assert_called_once_with(
        spreadsheetId="1",
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": "A1:B2", "values": values}],
        },
    )
    assert result == {"totalUpdatedCells": 4}


def test_batch_update_values_with_defaults(sheets_client):
    batch_update_call = sheets_client.values.batchUpdate
    batch_update_call.return_value.execute.return_value = {}
    values = [["a", "b"], ["c", "d"]]

    sheets.batch_update_values("1", "A1:B2", values)

    batch_update_call.assert_called_once_with(
        spreadsheetId="1",
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": "A1:B2", "values": values}],
        },
    )


def test_batch_update_values_passes_delegated_user_email(sheets_client):
    sheets_client.values.batchUpdate.return_value.execute.return_value = {}

    sheets.batch_update_values("1", "A1:B2", [["a"]], delegated_user_email="custom@example.com")

    sheets_client.factory.assert_called_once_with(scopes=SHEETS_SCOPES, delegated_user_email="custom@example.com")


def test_batch_update_values_propagates_http_error(sheets_client):
    error = _http_error(429)
    sheets_client.values.batchUpdate.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        sheets.batch_update_values("1", "A1:B2", [["a"]])

    assert exc_info.value is error


def test_append_values_returns_result(sheets_client):
    append_call = sheets_client.values.append
    append_call.return_value.execute.return_value = {"updates": {"updatedRows": 2}}
    body = {"values": [["a", "b"], ["c", "d"]]}

    result = sheets.append_values("1", "A1:B2", body)

    sheets_client.factory.assert_called_once_with(scopes=SHEETS_SCOPES, delegated_user_email=None)
    append_call.assert_called_once_with(
        spreadsheetId="1",
        range="A1:B2",
        body=body,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
    )
    assert result == {"updates": {"updatedRows": 2}}


def test_append_values_passes_delegated_user_email(sheets_client):
    sheets_client.values.append.return_value.execute.return_value = {}

    sheets.append_values("1", "A1:B2", {"values": []}, delegated_user_email="custom@example.com")

    sheets_client.factory.assert_called_once_with(scopes=SHEETS_SCOPES, delegated_user_email="custom@example.com")


def test_append_values_propagates_http_error(sheets_client):
    error = _http_error(429)
    sheets_client.values.append.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        sheets.append_values("1", "A1:B2", {"values": []})

    assert exc_info.value is error


def test_sheets_module_does_not_use_legacy_dispatcher():
    assert not hasattr(sheets, "execute_google_api_call")
