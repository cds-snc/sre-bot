"""The Google Docs adapter's bounded timeline rewrite, over a stub Docs service.

``update_timeline_section`` reads the report, rewrites the section between the markers
and writes it under a revision guard. The Docs service factory (the gateway edge) is
replaced by ``StubDocs``, which applies batchUpdate requests to real characters with
UTF-16 indexes and refuses a stale revision with a 400 as Docs does; the incident core
settings function (a settings seam) supplies the recompute bound. ``time.sleep`` and
``asyncio.sleep`` fail if called, so a passing test proves the recompute never waits.
Assertions are on the document text, the number of writes, and the classified result.
"""

import asyncio
import time
from collections.abc import Callable, Iterator

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from features.incident.common.settings import IncidentCoreSettings
from features.incident.core.adapters import google_docs
from tests.factories.incident_report_docs import StubDocs, google_http_error

pytestmark = pytest.mark.unit

DOCUMENT_ID = "D0REPORT"
LINK = "https://example.slack.com/archives/C123/p{}"


def _line(ts: str, text: str) -> str:
    return f"\n ➡️ [2026-10-02 16:02:00 ET]({LINK.format(ts.replace('.', ''))}) Jane Doe: {text}\n"


def _add(ts: str, text: str) -> Callable[[str], str | None]:
    return lambda content: google_docs.timeline_with_entry(content, LINK.format(ts.replace(".", "")), _line(ts, text))


@pytest.fixture
def attempts() -> list[int]:
    """The configured recompute bound; a test may replace its single value before updating."""
    return [3]


@pytest.fixture
def docs(monkeypatch: pytest.MonkeyPatch, attempts: list[int]) -> Iterator[StubDocs]:
    stub = StubDocs(DOCUMENT_ID)
    monkeypatch.setattr(google_docs, "get_docs_service", lambda scopes: stub.service)
    monkeypatch.setattr(
        google_docs, "get_incident_core_settings", lambda: IncidentCoreSettings(timeline_update_attempts=attempts[0])
    )

    def no_sleep(*_args: object) -> None:
        raise AssertionError("the timeline update must not sleep")

    monkeypatch.setattr(time, "sleep", no_sleep)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    yield stub


def test_an_entry_is_written_once_and_linked(docs: StubDocs) -> None:
    result = google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first"))

    assert result.is_success
    assert docs.timeline().count("first") == 1
    assert docs.links() == [LINK.format("1759435320000100")]
    assert docs.write_attempts == 1


def test_an_empty_section_accepts_its_first_entry(docs: StubDocs) -> None:
    docs.set_timeline("")

    assert google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first")).is_success
    assert docs.timeline().count("first") == 1


def test_no_change_reads_and_writes_nothing(docs: StubDocs) -> None:
    result = google_docs.update_timeline_section(DOCUMENT_ID, lambda _content: None)

    assert result.is_success
    assert docs.write_attempts == 0


def test_a_contended_write_lands_on_the_last_allowed_attempt_from_a_fresh_read(docs: StubDocs) -> None:
    """Two lost revision guards are each re-read and recomputed; a read precedes every write."""

    def compete() -> None:
        if docs.write_attempts <= 2:
            docs.revision += 1

    docs.before_write = compete

    result = google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first"))

    assert result.is_success
    assert docs.write_attempts == 3
    assert docs.reads == 3
    assert docs.timeline().count("first") == 1


@pytest.mark.parametrize("bound", [1, 3, 5])
def test_every_write_lost_stops_at_the_configured_bound(docs: StubDocs, attempts: list[int], bound: int) -> None:
    """[incident_core] timeline_update_attempts bounds the writes; a final read reconciles the last."""
    attempts[0] = bound
    docs.before_write = lambda: setattr(docs, "revision", docs.revision + 1)

    result = google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first"))

    assert not result.is_success
    assert result.status is OperationStatus.PERMANENT_ERROR and result.error_code == ErrorCode.HTTP_ERROR
    assert docs.write_attempts == bound
    assert docs.reads == bound + 1
    assert "first" not in docs.timeline()


def test_a_timeout_that_landed_is_reconciled_without_a_duplicate(docs: StubDocs) -> None:
    docs.confirm_write = lambda: False

    result = google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first"))

    assert result.is_success
    assert docs.timeline().count("first") == 1
    assert docs.write_attempts == 1


def test_a_write_landing_on_the_last_attempt_unconfirmed_is_reconciled_by_a_final_read(docs: StubDocs) -> None:
    docs.before_write = lambda: setattr(docs, "revision", docs.revision + (docs.write_attempts < 3))
    docs.confirm_write = lambda: False

    result = google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first"))

    assert result.is_success
    assert docs.timeline().count("first") == 1
    assert docs.write_attempts == 3


def test_an_unconfirmed_write_with_an_unreadable_reconcile_reports_the_timeout(docs: StubDocs) -> None:
    """The edit may have landed, so the result says unconfirmed, not refused."""

    def unconfirmed() -> bool:
        docs.unreadable = True
        return False

    docs.confirm_write = unconfirmed

    result = google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first"))

    assert result.status is OperationStatus.TRANSIENT_ERROR and result.error_code == ErrorCode.TIMEOUT


def test_a_refused_edit_on_an_unmoved_document_is_not_sent_again(docs: StubDocs) -> None:
    """A 400 while the revision did not move is a malformed edit, not a lost guard."""
    docs.fail_write = google_http_error(400)

    result = google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first"))

    assert result.error_code == ErrorCode.HTTP_ERROR
    assert docs.write_attempts == 1


@pytest.mark.parametrize("status", [403, 404, 429])
def test_other_write_failures_stop_after_one_write(docs: StubDocs, status: int) -> None:
    """Transport retries belong to the SDK, so a failure it gave up on is not sent again here."""
    docs.fail_write = google_http_error(status)

    result = google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first"))

    assert not result.is_success
    assert docs.write_attempts == 1


def test_an_unreadable_report_is_document_unreadable_and_writes_nothing(docs: StubDocs) -> None:
    result = google_docs.update_timeline_section("D0OTHER", _add("1759435320.000100", "first"))

    assert result.status is OperationStatus.TRANSIENT_ERROR and result.error_code == ErrorCode.DOCUMENT_UNREADABLE
    assert docs.write_attempts == 0


def test_a_report_without_the_markers_is_range_not_found_and_writes_nothing(docs: StubDocs) -> None:
    docs.chars = [(char, None) for char in "no markers\n"]

    result = google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first"))

    assert result.status is OperationStatus.PERMANENT_ERROR and result.error_code == ErrorCode.RANGE_NOT_FOUND
    assert docs.write_attempts == 0


def test_a_concurrent_human_edit_survives_the_recompute(docs: StubDocs) -> None:
    def human_edit() -> None:
        if docs.write_attempts == 1:
            at = docs.text().index(google_docs.TIMELINE_END_HEADING)
            docs.chars[at:at] = [(char, None) for char in "Human note\n"]
            docs.revision += 1

    docs.before_write = human_edit

    assert google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first")).is_success
    assert "Human note" in docs.timeline()
    assert docs.timeline().count("first") == 1


def test_non_bmp_text_keeps_later_entries_and_their_links_aligned(docs: StubDocs) -> None:
    google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435320.000100", "first 😀"))
    google_docs.update_timeline_section(DOCUMENT_ID, _add("1759435380.000200", "second"))

    lines = docs.timeline().splitlines()
    assert any(line.endswith("Jane Doe: first 😀") for line in lines)
    assert any(line.endswith("Jane Doe: second") for line in lines)
    assert docs.links() == [LINK.format("1759435320000100"), LINK.format("1759435380000200")]
    extracted = google_docs.extract_timeline_section(docs.content())
    assert extracted is not None and f"]({LINK.format('1759435380000200')})" in extracted
