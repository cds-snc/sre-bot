"""One behaviour suite for the report timeline methods: the Google Docs adapter and the in-memory fake.

The adapter runs over ``StubDocs`` (the gateway's Docs factory replaced in the adapter
module) holding one report whose timeline section starts empty, with UTF-16 indexes;
the fake knows the same report. Each test runs against both and reads the timeline
back as (entry identity, rendered author and text) pairs in report order: from the
stub's document through the adapter's own section reader, and from the fake's
``timeline_of``. So a consumer tested on the fake sees the adapter's rules: an entry
is held once per message (channel and Slack ts), entries read back chronologically,
removal deletes only that message and an absent one is a success, and an entry the
report cannot hold (no message link, a system entry) or a report of another system is
``UNSUPPORTED_OPERATION``; an unknown report is ``DOCUMENT_UNREADABLE``.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import IncidentCoreSettings
from features.incident.common.vocabulary import Severity
from features.incident.core.adapters import google_docs
from features.incident.core.adapters.in_memory import InMemoryIncidentReport
from features.incident.core.api import (
    IncidentReport,
    MessageReference,
    ReportReference,
    SeverityChange,
    TimelineEntry,
    TimelineEntryKind,
)
from tests.factories.incident_report_docs import StubDocs

pytestmark = pytest.mark.unit

TENANT = "C0GOOGLE"
REPORT = ReportReference(
    system=WorkplaceSystem.GOOGLE, tenant=TENANT, vendor_id="D0REPORT", url="https://docs.google.com/document/d/D0REPORT/edit"
)
UNKNOWN = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=TENANT, vendor_id="D0UNKNOWN")
SLACK_REPORT = ReportReference(system=WorkplaceSystem.SLACK, tenant="T0SLACK", vendor_id="F0FILE")
LINK = "https://example.slack.com/archives/C123/p{}"


def _message(ts: str, *, url: bool = True) -> MessageReference:
    return MessageReference(
        system=WorkplaceSystem.SLACK,
        tenant="T0SLACK",
        conversation_id="C123",
        message_id=ts,
        url=LINK.format(ts.replace(".", "")) if url else None,
    )


def _entry(ts: str, text: str, *, author: str = "Jane Doe", url: bool = True) -> TimelineEntry:
    return TimelineEntry(
        incident_id="I0INCIDENT",
        entry_id=f"e-{ts}",
        posted_at=datetime.fromtimestamp(float(ts), tz=UTC),
        author=author,
        text=text,
        source_message=_message(ts, url=url),
    )


@pytest.fixture
def stub_docs(monkeypatch: pytest.MonkeyPatch) -> Iterator[StubDocs]:
    stub = StubDocs(REPORT.vendor_id)
    monkeypatch.setattr(google_docs, "get_docs_service", lambda scopes: stub.service)
    monkeypatch.setattr(google_docs, "get_incident_core_settings", lambda: IncidentCoreSettings())
    yield stub


@pytest.fixture(params=["google", "in_memory"])
def report_interface(request: pytest.FixtureRequest) -> IncidentReport:
    if request.param == "google":
        request.getfixturevalue("stub_docs")
        return google_docs.GoogleDocsIncidentReport()
    fake = InMemoryIncidentReport(tenant=TENANT)
    fake.seed_sections(REPORT, [])
    return fake


def _timeline(report_interface: IncidentReport, request: pytest.FixtureRequest) -> list[tuple[Any, str]]:
    """Return (identity, ' author: text') per entry, in report order."""
    if isinstance(report_interface, InMemoryIncidentReport):
        return [
            (google_docs.timeline_message_key(entry.source_message.url or ""), f" {entry.author}: {entry.text}")
            for entry in report_interface.timeline_of(REPORT)
            if entry.source_message is not None
        ]
    stub: StubDocs = request.getfixturevalue("stub_docs")
    section = google_docs.extract_timeline_section(stub.content()) or ""
    return [
        (google_docs.timeline_message_key(match["url"]), section[match.end() : section.find("\n", match.end())])
        for match in google_docs.TIMELINE_ENTRY_PATTERN.finditer(section)
    ]


def _key(ts: str) -> tuple[str, str]:
    return ("C123", ts.replace(".", ""))


async def test_an_appended_entry_reads_back_once(report_interface: IncidentReport, request: pytest.FixtureRequest) -> None:
    result = await report_interface.append_timeline_entry(REPORT, _entry("1759435320.000100", "first"))

    assert result.is_success
    assert _timeline(report_interface, request) == [(_key("1759435320.000100"), " Jane Doe: first")]


async def test_appending_the_same_message_again_changes_nothing(
    report_interface: IncidentReport, request: pytest.FixtureRequest
) -> None:
    await report_interface.append_timeline_entry(REPORT, _entry("1759435320.000100", "first"))

    again = await report_interface.append_timeline_entry(REPORT, _entry("1759435320.000100", "edited", author="New Name"))

    assert again.is_success
    assert _timeline(report_interface, request) == [(_key("1759435320.000100"), " Jane Doe: first")]


async def test_entries_read_back_in_chronological_order(report_interface: IncidentReport, request: pytest.FixtureRequest) -> None:
    await report_interface.append_timeline_entry(REPORT, _entry("1759435380.000200", "second"))
    await report_interface.append_timeline_entry(REPORT, _entry("1759435320.000100", "first"))

    assert [key for key, _ in _timeline(report_interface, request)] == [_key("1759435320.000100"), _key("1759435380.000200")]


async def test_non_bmp_text_round_trips(report_interface: IncidentReport, request: pytest.FixtureRequest) -> None:
    await report_interface.append_timeline_entry(REPORT, _entry("1759435320.000100", "first 😀"))
    await report_interface.append_timeline_entry(REPORT, _entry("1759435380.000200", "second 🚀"))

    assert _timeline(report_interface, request) == [
        (_key("1759435320.000100"), " Jane Doe: first 😀"),
        (_key("1759435380.000200"), " Jane Doe: second 🚀"),
    ]


async def test_removal_deletes_only_that_message(report_interface: IncidentReport, request: pytest.FixtureRequest) -> None:
    await report_interface.append_timeline_entry(REPORT, _entry("1759435320.000100", "first"))
    await report_interface.append_timeline_entry(REPORT, _entry("1759435380.000200", "second"))

    removed = await report_interface.remove_timeline_entry(REPORT, _message("1759435320.000100"))

    assert removed.is_success
    assert _timeline(report_interface, request) == [(_key("1759435380.000200"), " Jane Doe: second")]


async def test_removing_an_absent_message_succeeds(report_interface: IncidentReport, request: pytest.FixtureRequest) -> None:
    await report_interface.append_timeline_entry(REPORT, _entry("1759435320.000100", "first"))

    removed = await report_interface.remove_timeline_entry(REPORT, _message("1759435380.000200"))

    assert removed.is_success
    assert len(_timeline(report_interface, request)) == 1


@pytest.mark.parametrize(
    "entry",
    [
        _entry("1759435320.000100", "no link", url=False),
        TimelineEntry(
            incident_id="I0INCIDENT",
            entry_id="manual",
            posted_at=datetime(2026, 11, 18, tzinfo=UTC),
            author="Jane Doe",
            text="manual note",
        ),
        TimelineEntry(
            incident_id="I0INCIDENT",
            entry_id="sev",
            posted_at=datetime(2026, 11, 18, tzinfo=UTC),
            author="U0ACTOR",
            text="",
            kind=TimelineEntryKind.SEVERITY_CHANGED,
            severity_change=SeverityChange(previous=None, current=Severity.SEV2),
        ),
    ],
    ids=["no-message-link", "manual", "severity-changed"],
)
async def test_an_entry_the_report_cannot_hold_is_unsupported(
    report_interface: IncidentReport, request: pytest.FixtureRequest, entry: TimelineEntry
) -> None:
    result = await report_interface.append_timeline_entry(REPORT, entry)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.UNSUPPORTED_OPERATION
    assert _timeline(report_interface, request) == []


async def test_removing_a_message_without_a_link_is_unsupported(report_interface: IncidentReport) -> None:
    result = await report_interface.remove_timeline_entry(REPORT, _message("1759435320.000100", url=False))

    assert result.error_code == ErrorCode.UNSUPPORTED_OPERATION


async def test_a_report_of_another_system_is_unsupported(report_interface: IncidentReport) -> None:
    appended = await report_interface.append_timeline_entry(SLACK_REPORT, _entry("1759435320.000100", "first"))
    removed = await report_interface.remove_timeline_entry(SLACK_REPORT, _message("1759435320.000100"))

    assert appended.error_code == removed.error_code == ErrorCode.UNSUPPORTED_OPERATION


async def test_an_unknown_report_is_document_unreadable(report_interface: IncidentReport) -> None:
    appended = await report_interface.append_timeline_entry(UNKNOWN, _entry("1759435320.000100", "first"))
    removed = await report_interface.remove_timeline_entry(UNKNOWN, _message("1759435320.000100"))

    for result in (appended, removed):
        assert result.status is OperationStatus.TRANSIENT_ERROR
        assert result.error_code == ErrorCode.DOCUMENT_UNREADABLE
