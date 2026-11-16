"""Behavior tests for where GoogleDocsIncidentReport runs its blocking Docs and Drive work.

The report is awaited from the event loop; each method's blocking Google work
runs in a worker thread. The gateway's Docs and Drive service factories (the
edge in ``integrations/``) are replaced by recorders that note the thread each
service is built on and hand back a ``MagicMock`` service. Every helper builds
its service inside the blocking work, so the recorded threads show where that
work ran; the method's result is not asserted, the mock answers being
arbitrary.
"""

import threading
from collections.abc import Callable, Coroutine
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from contracts.operations.result import OperationResult
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import IncidentCoreSettings
from features.incident.core.adapters import google_docs
from features.incident.core.api import ReportReference, SectionDraft

pytestmark = pytest.mark.unit

TENANT = "C0GOOGLE"
REPORT = ReportReference(
    system=WorkplaceSystem.GOOGLE,
    tenant=TENANT,
    vendor_id="D0REPORT",
    url="https://docs.google.com/document/d/D0REPORT/edit",
)
DRAFT = SectionDraft(heading="Summary", content="What happened.", is_drafted=True)

type ReportCall = Callable[[google_docs.GoogleDocsIncidentReport], Coroutine[Any, Any, OperationResult[Any]]]

CALLS: dict[str, ReportCall] = {
    "list_placements": lambda report: report.list_placements(),
    "create_from_template": lambda report: report.create_from_template("2026-11-16 Incident"),
    "replace_placeholders": lambda report: report.replace_placeholders(REPORT, {"{{title}}": "Outage"}),
    "read_sections": lambda report: report.read_sections(REPORT),
    "write_draft_copy": lambda report: report.write_draft_copy(REPORT, [DRAFT], [], {}),
}


@pytest.fixture
def service_threads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Record the thread every Docs or Drive service is built on."""
    threads: list[int] = []

    def recording_factory(scopes: Any) -> MagicMock:
        threads.append(threading.get_ident())
        service = MagicMock()
        service.files.return_value.list_next.return_value = None
        return service

    # The module reaches the Docs service under both names: placeholder edits and the section reader.
    monkeypatch.setattr(google_docs, "get_docs_service", recording_factory)
    monkeypatch.setattr(google_docs.google_workspace_client, "get_docs_service", recording_factory)
    monkeypatch.setattr(google_docs.google_workspace_client, "get_drive_service", recording_factory)
    monkeypatch.setattr(
        google_docs,
        "get_incident_core_settings",
        lambda: IncidentCoreSettings(folder_id="F0INCIDENTS", report_template_id="T0TEMPLATE"),
    )
    monkeypatch.setattr(
        google_docs, "get_google_workspace_settings", lambda: SimpleNamespace(tenant=SimpleNamespace(customer_id=TENANT))
    )
    return threads


@pytest.mark.parametrize("method", list(CALLS))
async def test_each_method_runs_its_google_calls_off_the_event_loop_thread(service_threads: list[int], method: str) -> None:
    await CALLS[method](google_docs.GoogleDocsIncidentReport())

    assert service_threads
    assert threading.get_ident() not in service_threads
