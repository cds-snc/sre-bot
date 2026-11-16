"""``update_status`` sets the Status cell of the incident's row, or writes the full row when there is none.

The Sheets service is a stateful stand-in at the gateway factory. A row keyed by
the incident id gets only D<n>; a legacy row found through its channel link also
gets F<n>, so it is keyed from then on; with no row the full row is appended
carrying the given status. The status is the argument, not the incident's own.
"""

import threading

import pytest

from contracts.operations.status import OperationStatus
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.google_sheets import GoogleSheetsIncidentListProjection
from tests.factories.incident_list_sheet import (
    CHANNEL_FORMULA,
    REPORT_FORMULA,
    SHEET_ID,
    FakeSheetsService,
    install_sheet,
    listed_incident,
)

pytestmark = pytest.mark.unit


async def test_row_found_by_id_gets_only_its_status_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only D<n> is written, user-entered, on the row keyed by the id."""
    sheet = FakeSheetsService([["d", "t", "p", "In Progress", "c", "other"], ["d", "t", "p", "In Progress", "c", "id-1"]])
    install_sheet(monkeypatch, sheet)

    result = await GoogleSheetsIncidentListProjection().update_status(listed_incident(), IncidentStatus.CLOSED)

    assert result.status is OperationStatus.SUCCESS
    (batch,) = sheet.sent("batchUpdate")
    assert batch.kwargs == {
        "spreadsheetId": SHEET_ID,
        "body": {"valueInputOption": "USER_ENTERED", "data": [{"range": "Sheet1!D3", "values": [["Closed"]]}]},
    }
    assert sheet.data_rows()[0][3] == "In Progress"
    assert sheet.data_rows()[1] == ["d", "t", "p", "Closed", "c", "id-1"]
    assert sheet.sent("append") == []


async def test_row_found_by_channel_is_keyed_with_the_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A legacy row found through its channel link gets its status and, with it, the incident id in F."""
    sheet = FakeSheetsService([["d", "t", "p", "In Progress", CHANNEL_FORMULA]])
    install_sheet(monkeypatch, sheet)

    await GoogleSheetsIncidentListProjection().update_status(listed_incident(), IncidentStatus.CLOSED)

    (batch,) = sheet.sent("batchUpdate")
    assert batch.kwargs["body"]["data"] == [
        {"range": "Sheet1!D2", "values": [["Closed"]]},
        {"range": "Sheet1!F2", "values": [["id-1"]]},
    ]
    assert sheet.data_rows() == [["d", "t", "p", "Closed", CHANNEL_FORMULA, "id-1"]]


async def test_missing_row_is_appended_in_full_with_the_given_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no row for the incident the whole row is written, carrying the status asked for."""
    sheet = FakeSheetsService()
    install_sheet(monkeypatch, sheet)

    result = await GoogleSheetsIncidentListProjection().update_status(listed_incident(), IncidentStatus.REVIEWED)

    assert result.status is OperationStatus.SUCCESS
    (append,) = sheet.sent("append")
    assert append.num_retries == 0
    assert sheet.data_rows() == [["2026-10-01", REPORT_FORMULA, "Notify", "Reviewed", CHANNEL_FORMULA, "id-1"]]


async def test_lookup_and_write_share_one_thread_off_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """One thread hop per call, never the event loop's thread; the lookup reads E:F as formulas."""
    sheet = FakeSheetsService([["d", "t", "p", "Open", "c", "id-1"]])
    install_sheet(monkeypatch, sheet)

    await GoogleSheetsIncidentListProjection().update_status(listed_incident(), IncidentStatus.CLOSED)

    (get,) = sheet.sent("get")
    assert get.kwargs["range"] == "Sheet1!E:F"
    assert get.kwargs["valueRenderOption"] == "FORMULA"
    threads = {request.thread for request in sheet.requests}
    assert len(threads) == 1
    assert threads != {threading.get_ident()}
