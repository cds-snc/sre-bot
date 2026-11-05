"""The scribe draft reads the incident report through the incident core's IncidentReport by default.

``get_incident_report`` is the core provider: constructing the Google Docs
adapter opens no Google client (services are built per call), so the real
provider runs and is checked against the runtime-checkable Protocol. The
service's default is then replaced on the service module, where it is looked up
at call time, by an in-memory report holding no sections, so no Google call is
made and the read is observable.
"""

from collections.abc import Iterator

import pytest

from contracts.operations import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.google_docs import GoogleDocsIncidentReport
from features.incident.core.adapters.in_memory import InMemoryIncidentReport
from features.incident.core.api import IncidentReport, ReportReference, TranscriptMessage, get_incident_report
from features.incident.scribe import service
from features.incident.scribe.service import DOCUMENT_UNREADABLE_CODE, draft_incident_document

pytestmark = pytest.mark.unit

REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="DOC1")


@pytest.fixture(autouse=True)
def _clear_report_cache() -> Iterator[None]:
    yield
    get_incident_report.cache_clear()


def test_the_core_provider_returns_one_cached_google_docs_report() -> None:
    reports = get_incident_report()

    assert isinstance(reports, GoogleDocsIncidentReport)
    assert isinstance(reports, IncidentReport)
    assert get_incident_report() is reports


async def test_the_service_reads_through_the_core_provider_when_no_report_interface_is_passed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A report with no sections maps to DOCUMENT_UNREADABLE and nothing is written."""
    reports = InMemoryIncidentReport()
    reports.seed_sections(REPORT, [])
    monkeypatch.setattr(service, "get_incident_report", lambda: reports)

    result = await draft_incident_document(REPORT, [TranscriptMessage(author="Ada", text="prod is down")])

    assert reports.read_from == [REPORT]
    assert reports.draft_copies == []
    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == DOCUMENT_UNREADABLE_CODE
