"""``append_row`` upserts the incident's full row on the list sheet.

The Sheets service is a stateful stand-in at the gateway factory; settings are
stubbed at their getters. The incident's row is looked up on E:F with formulas
rendered as typed: found, it is rewritten in place (A:F, retryable because it
is idempotent); not found, it is appended with ``INSERT_ROWS`` and no SDK retry,
since an append has no idempotency key. An incident missing its report,
conversation or product is written with blank or plain cells.
"""

import threading

import pytest

from contracts.operations.status import OperationStatus
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

ROW = ["2026-10-01", REPORT_FORMULA, "Notify", "In Progress", CHANNEL_FORMULA, "id-1"]


async def test_missing_row_is_appended_with_the_pinned_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """No row for the id: one append at A:A, user-entered so formulas evaluate, rows inserted, no SDK retry."""
    sheet = FakeSheetsService()
    install_sheet(monkeypatch, sheet)

    result = await GoogleSheetsIncidentListProjection().append_row(listed_incident())

    assert result.status is OperationStatus.SUCCESS
    (append,) = sheet.sent("append")
    assert append.kwargs == {
        "spreadsheetId": SHEET_ID,
        "range": "Sheet1!A:A",
        "valueInputOption": "USER_ENTERED",
        "insertDataOption": "INSERT_ROWS",
        "body": {"values": [ROW]},
    }
    assert append.num_retries == 0
    assert sheet.data_rows() == [ROW]


async def test_lookup_reads_columns_e_and_f_as_formulas(monkeypatch: pytest.MonkeyPatch) -> None:
    """The row is located on E:F with the formulas as typed, never the rendered values."""
    sheet = FakeSheetsService()
    install_sheet(monkeypatch, sheet)

    await GoogleSheetsIncidentListProjection().append_row(listed_incident())

    (get,) = sheet.sent("get")
    assert get.kwargs == {"spreadsheetId": SHEET_ID, "range": "Sheet1!E:F", "valueRenderOption": "FORMULA"}
    assert get.num_retries is None


async def test_existing_row_is_rewritten_in_place(monkeypatch: pytest.MonkeyPatch) -> None:
    """A row keyed by the id is updated at A<n>:F<n>, nothing appended, other rows untouched."""
    other = ["2026-09-01", "x", "", "Closed", "", "id-0"]
    sheet = FakeSheetsService([other, ["old", "old", "old", "Open", "old", "id-1"]])
    install_sheet(monkeypatch, sheet)

    await GoogleSheetsIncidentListProjection().append_row(listed_incident())

    (update,) = sheet.sent("update")
    assert update.kwargs["range"] == "Sheet1!A3:F3"
    assert update.kwargs["valueInputOption"] == "USER_ENTERED"
    assert update.num_retries is None
    assert sheet.sent("append") == []
    assert sheet.data_rows() == [other, ROW]


async def test_legacy_row_without_id_is_rewritten_and_keyed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A legacy row of the same channel is found by its link and rewritten with the id in F."""
    sheet = FakeSheetsService([["2026-10-01", "x", "", "Open", CHANNEL_FORMULA]])
    install_sheet(monkeypatch, sheet)

    await GoogleSheetsIncidentListProjection().append_row(listed_incident())

    assert sheet.data_rows() == [ROW]


async def test_incident_without_conversation_or_report_is_written_not_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without report, conversation and product the row has the plain title and blank cells."""
    sheet = FakeSheetsService()
    install_sheet(monkeypatch, sheet)

    result = await GoogleSheetsIncidentListProjection().append_row(listed_incident(report=False, channel=None, product=None))

    assert result.status is OperationStatus.SUCCESS
    assert sheet.data_rows() == [["2026-10-01", "Database outage", "", "In Progress", "", "id-1"]]


async def test_all_requests_of_a_call_run_in_one_thread_off_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lookup and the write share one thread hop, and it is not the event loop's thread."""
    sheet = FakeSheetsService()
    install_sheet(monkeypatch, sheet)

    await GoogleSheetsIncidentListProjection().append_row(listed_incident())

    threads = {request.thread for request in sheet.requests}
    assert len(threads) == 1
    assert threads != {threading.get_ident()}
