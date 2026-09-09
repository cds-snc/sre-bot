"""Behavior contract for the Google-backed SpreadsheetProvider implementation."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest

from infrastructure.operations.status import OperationStatus
from infrastructure.spreadsheets.google import GoogleSpreadsheetProvider
from infrastructure.spreadsheets.models import SheetCell
from infrastructure.spreadsheets.provider import SpreadsheetProvider
from integrations.google_workspace import client as google_client_module


class FakeResp(dict):
    def __init__(self, status: int, reason: str = "boom") -> None:
        super().__init__()
        self.status = status
        self.reason = reason


def _http_error(status: int, reason: str = "boom") -> HttpError:
    return HttpError(resp=FakeResp(status, reason), content=b"{}")


def _request(payload: object | None = None) -> MagicMock:
    request = MagicMock()
    request.execute.return_value = {} if payload is None else payload
    return request


@pytest.fixture
def spreadsheet_service() -> MagicMock:
    service = MagicMock()
    values = service.spreadsheets.return_value.values.return_value
    values.get.return_value = _request({"values": [["Name", "12"], ["Case", "7"]]})
    values.batchUpdate.return_value = _request({})
    values.append.return_value = _request({})
    service.spreadsheets.return_value.get.return_value = _request(
        {
            "sheets": [
                {
                    "data": [
                        {
                            "rowData": [
                                {
                                    "values": [
                                        {"formattedValue": "Name", "hyperlink": "https://example.test/name"},
                                        {"formattedValue": "12"},
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    )
    return service


@pytest.fixture
def provider(spreadsheet_service: MagicMock) -> GoogleSpreadsheetProvider:
    return GoogleSpreadsheetProvider(
        get_service=MagicMock(return_value=spreadsheet_service),
        spreadsheet_settings=MagicMock(),
    )


def test_provider_satisfies_spreadsheet_protocol_without_drive_liveness_methods(
    provider: GoogleSpreadsheetProvider,
) -> None:
    assert isinstance(provider, SpreadsheetProvider)
    assert not hasattr(provider, "warmup")
    assert not hasattr(provider, "health_check")


def test_read_values_returns_string_matrix_and_uses_a1_range(
    provider: GoogleSpreadsheetProvider, spreadsheet_service: MagicMock
) -> None:
    result = provider.read_values("sheet-id", "Sheet1!A:A")

    assert result.is_success
    assert result.data == [["Name", "12"], ["Case", "7"]]
    spreadsheet_service.spreadsheets.return_value.values.return_value.get.assert_called_once_with(
        spreadsheetId="sheet-id", range="Sheet1!A:A"
    )
    spreadsheet_service.spreadsheets.return_value.values.return_value.get.return_value.execute.assert_called_once_with()


def test_read_values_returns_empty_matrix_when_values_are_absent(provider: GoogleSpreadsheetProvider) -> None:
    request = MagicMock()
    request.execute.return_value = {}
    provider._get_service.return_value.spreadsheets.return_value.values.return_value.get.return_value = request

    result = provider.read_values("sheet-id", "Sheet1")

    assert result.is_success
    assert result.data == []


def test_read_values_coerces_non_string_cells_to_strings(provider: GoogleSpreadsheetProvider) -> None:
    request = MagicMock()
    request.execute.return_value = {"values": [[1, True, None]]}
    provider._get_service.return_value.spreadsheets.return_value.values.return_value.get.return_value = request

    result = provider.read_values("sheet-id", "Sheet1")

    assert result.is_success
    assert result.data == [["1", "True", "None"]]


def test_update_values_sends_expected_batch_body(provider: GoogleSpreadsheetProvider, spreadsheet_service: MagicMock) -> None:
    values = [["Case", "Open"]]

    result = provider.update_values("sheet-id", "Sheet1!A:B", values)

    assert result.is_success
    assert result.data is None
    spreadsheet_service.spreadsheets.return_value.values.return_value.batchUpdate.assert_called_once_with(
        spreadsheetId="sheet-id",
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": "Sheet1!A:B", "values": values}],
        },
    )


def test_append_values_preserves_hyperlink_formula_and_append_options(
    provider: GoogleSpreadsheetProvider, spreadsheet_service: MagicMock
) -> None:
    values = [["Case", '=HYPERLINK("https://example.test/case", "Case")']]

    result = provider.append_values("sheet-id", "Sheet1!A:B", values)

    assert result.is_success
    spreadsheet_service.spreadsheets.return_value.values.return_value.append.assert_called_once_with(
        spreadsheetId="sheet-id",
        range="Sheet1!A:B",
        body={"majorDimension": "ROWS", "values": values},
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
    )


def test_read_cells_maps_formatted_values_and_optional_hyperlinks(
    provider: GoogleSpreadsheetProvider, spreadsheet_service: MagicMock
) -> None:
    result = provider.read_cells("sheet-id", "Sheet1!A:B")

    assert result.is_success
    assert result.data == [
        [
            SheetCell(formatted_value="Name", link="https://example.test/name", provider="google"),
            SheetCell(formatted_value="12", link=None, provider="google"),
        ]
    ]
    spreadsheet_service.spreadsheets.return_value.get.assert_called_once_with(
        spreadsheetId="sheet-id", ranges="Sheet1!A:B", includeGridData=True
    )


@pytest.mark.parametrize("payload", [{}, {"sheets": [{}]}, {"sheets": [{"data": [{}]}]}])
def test_read_cells_returns_empty_matrix_for_missing_grid_levels(
    provider: GoogleSpreadsheetProvider, payload: dict[str, object]
) -> None:
    request = MagicMock()
    request.execute.return_value = payload
    provider._get_service.return_value.spreadsheets.return_value.get.return_value = request

    result = provider.read_cells("sheet-id", "Sheet1")

    assert result.is_success
    assert result.data == []


def test_parse_range_error_maps_to_not_found_for_read_values(provider: GoogleSpreadsheetProvider) -> None:
    request = MagicMock()
    request.execute.side_effect = _http_error(400, "Unable to parse range: Sheet1!bad")
    provider._get_service.return_value.spreadsheets.return_value.values.return_value.get.return_value = request

    result = provider.read_values("sheet-id", "Sheet1!bad")

    assert result.status == OperationStatus.NOT_FOUND
    assert result.error_code == "RANGE_NOT_FOUND"


def test_parse_range_error_maps_to_not_found_for_read_cells(provider: GoogleSpreadsheetProvider) -> None:
    request = MagicMock()
    request.execute.side_effect = _http_error(400, "Unable to parse range: Sheet1!bad")
    provider._get_service.return_value.spreadsheets.return_value.get.return_value = request

    result = provider.read_cells("sheet-id", "Sheet1!bad")

    assert result.status == OperationStatus.NOT_FOUND
    assert result.error_code == "RANGE_NOT_FOUND"


def test_not_found_error_uses_shared_google_classification(provider: GoogleSpreadsheetProvider) -> None:
    request = MagicMock()
    request.execute.side_effect = _http_error(404)
    provider._get_service.return_value.spreadsheets.return_value.values.return_value.get.return_value = request

    result = provider.read_values("sheet-id", "Sheet1")

    assert result.status == OperationStatus.NOT_FOUND
    assert result.error_code == "404"


def test_rate_limit_error_preserves_shared_retry_metadata(provider: GoogleSpreadsheetProvider) -> None:
    request = MagicMock()
    error = _http_error(429)
    error.resp["retry-after"] = "11"
    request.execute.side_effect = error
    provider._get_service.return_value.spreadsheets.return_value.values.return_value.get.return_value = request

    result = provider.read_values("sheet-id", "Sheet1")

    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "429"
    assert result.retry_after == 11


def test_unmapped_http_error_propagates(provider: GoogleSpreadsheetProvider) -> None:
    request = MagicMock()
    request.execute.side_effect = _http_error(400, "Invalid argument")
    provider._get_service.return_value.spreadsheets.return_value.values.return_value.get.return_value = request

    with pytest.raises(HttpError):
        provider.read_values("sheet-id", "Sheet1")


def test_sheets_factory_resource_inherits_configured_retry_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    settings = SimpleNamespace(
        GCP_SRE_SERVICE_ACCOUNT_KEY_FILE='{"client_email":"sre-bot@example.com","private_key":"FAKE"}',
        SRE_BOT_EMAIL="sre-bot@example.com",
        GOOGLE_API_NUM_RETRIES=3,
    )

    class FakeCredentials:
        def with_scopes(self, scopes: list[str]) -> FakeCredentials:
            return self

        def with_subject(self, subject: str) -> FakeCredentials:
            return self

    monkeypatch.setattr(google_client_module, "get_google_workspace_settings", lambda: settings)
    monkeypatch.setattr(
        google_client_module.service_account.Credentials,
        "from_service_account_info",
        lambda info: FakeCredentials(),
    )
    monkeypatch.setattr(
        google_client_module,
        "build",
        lambda *args, **kwargs: captured.update(kwargs) or MagicMock(),
    )

    google_client_module.get_sheets_service(scopes=["https://www.googleapis.com/auth/spreadsheets"])

    assert callable(captured["requestBuilder"])
    retry_counts: list[int] = []
    monkeypatch.setattr(
        HttpRequest,
        "execute",
        lambda self, http=None, num_retries=0, **kwargs: retry_counts.append(num_retries) or {"ok": True},
    )
    request = captured["requestBuilder"](None, MagicMock(), "https://example.test")

    assert request.execute() == {"ok": True}
    assert retry_counts == [3]
