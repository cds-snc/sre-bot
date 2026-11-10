"""One behaviour suite for every IncidentReport: the Google Docs adapter and the in-memory fake.

The adapter runs over stubbed Docs and Drive services (the gateway factories are
replaced in the adapter module), the configured incident document ids and a
configured Google tenant; the fake is built with the same ids and tenant. Each
test runs against both, so a consumer tested on the fake sees the adapter's
observable rules: a created report is a Google reference under the configured
tenant with its Docs link, a reference of another system is refused as
unsupported, an unknown report is not found, and the link is the stored url.
Both know the same placements (the incident folder's subfolders other than
Templates), listed by label, and a report can be created in one of them.
"""

from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import IncidentCoreSettings
from features.incident.core.adapters import google_docs
from features.incident.core.adapters.in_memory import InMemoryIncidentReport
from features.incident.core.api import DocumentSection, IncidentReport, ReportPlacement, ReportReference, SectionDraft

pytestmark = pytest.mark.unit

TENANT = "C0GOOGLE"
FOLDER_ID = "F0INCIDENTS"
TEMPLATE_ID = "T0TEMPLATE"
CREATED_ID = "D0CREATED"
FOLDERS = [{"id": "F0NOTIFY", "name": "Notify"}, {"id": "F0TEMPLATES", "name": "Templates"}, {"id": "F0APPS", "name": "Apps"}]
APPS = ReportPlacement(
    system=WorkplaceSystem.GOOGLE,
    tenant=TENANT,
    vendor_id="F0APPS",
    url="https://drive.google.com/drive/folders/F0APPS",
    label="Apps",
)
NOTIFY = ReportPlacement(
    system=WorkplaceSystem.GOOGLE,
    tenant=TENANT,
    vendor_id="F0NOTIFY",
    url="https://drive.google.com/drive/folders/F0NOTIFY",
    label="Notify",
)
SLACK_REPORT = ReportReference(system=WorkplaceSystem.SLACK, tenant="T0SLACK", vendor_id="F0FILE")


def _http_error(status: int) -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = "boom"

    return HttpError(resp=cast(Any, FakeResp()), content=b"{}")


def _heading(text: str) -> dict[str, Any]:
    return {"paragraph": {"paragraphStyle": {"namedStyleType": "HEADING_1"}, "elements": [{"textRun": {"content": text}}]}}


def _body(text: str) -> dict[str, Any]:
    return {"paragraph": {"paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "elements": [{"textRun": {"content": text}}]}}


class _StubGoogle:
    """Docs and Drive services that know one report, ``CREATED_ID``, once it was copied from the template."""

    def __init__(self) -> None:
        self.created = False
        self.docs = MagicMock()
        self.drive = MagicMock()
        self.drive.files.return_value.copy.side_effect = self._copy
        self.drive.files.return_value.list.side_effect = self._list
        self.drive.files.return_value.list_next.return_value = None
        self.docs.documents.return_value.get.side_effect = self._get
        self.docs.documents.return_value.batchUpdate.side_effect = self._batch_update

    def _copy(self, **kwargs: Any) -> MagicMock:
        request = MagicMock()
        if kwargs["fileId"] == TEMPLATE_ID:
            self.created = True
            request.execute.return_value = {"id": CREATED_ID, "name": kwargs["body"]["name"]}
        else:
            request.execute.side_effect = _http_error(404)
        return request

    def _list(self, **kwargs: Any) -> MagicMock:
        request = MagicMock()
        if f"parents in '{FOLDER_ID}'" in kwargs["q"] and "mimeType = " in kwargs["q"]:
            request.execute.return_value = {"files": FOLDERS}
        else:
            request.execute.return_value = {"files": []}
        return request

    def _get(self, documentId: str) -> MagicMock:
        request = MagicMock()
        if self.created and documentId == CREATED_ID:
            request.execute.return_value = {
                "revisionId": "r1",
                "body": {"content": [_heading("Summary\n"), _body("What happened.\n"), _heading("Impact\n")]},
            }
        else:
            request.execute.side_effect = _http_error(404)
        return request

    def _batch_update(self, documentId: str, body: Any) -> MagicMock:
        request = MagicMock()
        if self.created and documentId == CREATED_ID:
            request.execute.return_value = {"replies": [{"replaceAllText": {"occurrencesChanged": 1}}]}
        else:
            request.execute.side_effect = _http_error(404)
        return request


@pytest.fixture
def google_adapter(monkeypatch: pytest.MonkeyPatch) -> Iterator[IncidentReport]:
    stub = _StubGoogle()
    # The module reaches the Docs service under both names: placeholder edits and the section reader.
    monkeypatch.setattr(google_docs, "get_docs_service", lambda scopes: stub.docs)
    monkeypatch.setattr(google_docs.google_workspace_client, "get_docs_service", lambda scopes: stub.docs)
    monkeypatch.setattr(google_docs.google_workspace_client, "get_drive_service", lambda scopes: stub.drive)
    monkeypatch.setattr(
        google_docs,
        "get_incident_core_settings",
        lambda: IncidentCoreSettings(folder_id=FOLDER_ID, report_template_id=TEMPLATE_ID),
    )
    monkeypatch.setattr(
        google_docs, "get_google_workspace_settings", lambda: SimpleNamespace(tenant=SimpleNamespace(customer_id=TENANT))
    )
    yield google_docs.GoogleDocsIncidentReport()


def _fake() -> IncidentReport:
    return InMemoryIncidentReport(
        tenant=TENANT,
        folder_id=FOLDER_ID,
        report_template_id=TEMPLATE_ID,
        next_ids=[CREATED_ID],
        placements=[("F0NOTIFY", "Notify"), ("F0APPS", "Apps")],
    )


@pytest.fixture(params=["google", "in_memory"])
def report_interface(request: pytest.FixtureRequest) -> IncidentReport:
    if request.param == "google":
        return request.getfixturevalue("google_adapter")
    return _fake()


def _created(report_interface: IncidentReport) -> ReportReference:
    result = report_interface.create_from_template("2026-11-05 Incident")
    assert result.is_success and result.data is not None
    return result.data


def test_both_implement_the_protocol(report_interface: IncidentReport) -> None:
    assert isinstance(report_interface, IncidentReport)


def test_a_created_report_is_a_google_reference_under_the_configured_tenant_with_its_docs_link(
    report_interface: IncidentReport,
) -> None:
    report = _created(report_interface)

    assert report == ReportReference(
        system=WorkplaceSystem.GOOGLE,
        tenant=TENANT,
        vendor_id=CREATED_ID,
        url=f"https://docs.google.com/document/d/{CREATED_ID}/edit",
    )


def test_a_created_report_reads_back_its_template_sections_in_order(report_interface: IncidentReport) -> None:
    report = _created(report_interface)
    if isinstance(report_interface, InMemoryIncidentReport):
        report_interface.seed_sections(report, [DocumentSection("Summary", "What happened.\n"), DocumentSection("Impact", "")])

    sections = report_interface.read_sections(report)

    assert sections.is_success
    assert [section.heading for section in sections.data or ()] == ["Summary", "Impact"]


def test_placeholders_on_a_created_report_succeed(report_interface: IncidentReport) -> None:
    report = _created(report_interface)

    assert report_interface.replace_placeholders(report, {"{{title}}": "Incident"}).is_success


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda r, ref: r.replace_placeholders(ref, {"a": "b"}), id="replace_placeholders"),
        pytest.param(lambda r, ref: r.read_sections(ref), id="read_sections"),
    ],
)
def test_an_unknown_google_report_is_not_found(
    report_interface: IncidentReport, call: Callable[[IncidentReport, ReportReference], Any]
) -> None:
    unknown = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=TENANT, vendor_id="D0UNKNOWN")

    result = call(report_interface, unknown)

    assert result.status is OperationStatus.NOT_FOUND


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda r, ref: r.replace_placeholders(ref, {"a": "b"}), id="replace_placeholders"),
        pytest.param(lambda r, ref: r.read_sections(ref), id="read_sections"),
        pytest.param(lambda r, ref: r.write_draft_copy(ref, [SectionDraft("Summary", "x", True)], (), {}), id="write_draft_copy"),
    ],
)
def test_a_report_of_another_system_is_unsupported(
    report_interface: IncidentReport, call: Callable[[IncidentReport, ReportReference], Any]
) -> None:
    result = call(report_interface, SLACK_REPORT)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.UNSUPPORTED_OPERATION


def test_a_draft_copy_with_nothing_to_write_fails(report_interface: IncidentReport) -> None:
    report = _created(report_interface)

    assert not report_interface.write_draft_copy(report, [], (), {}).is_success


def test_the_link_is_the_stored_url_and_none_without_one(report_interface: IncidentReport) -> None:
    stored = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=TENANT, vendor_id="D1", url="https://example.test/d/D1")
    bare = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=TENANT, vendor_id="D1")

    assert report_interface.link(stored) == "https://example.test/d/D1"
    assert report_interface.link(bare) is None


def test_placements_are_the_incident_folders_subfolders_by_label(report_interface: IncidentReport) -> None:
    placements = report_interface.list_placements()

    assert placements.is_success
    assert placements.data == (APPS, NOTIFY)


@pytest.mark.parametrize("placement", [None, APPS])
def test_a_report_is_created_with_or_without_a_placement(
    report_interface: IncidentReport, placement: ReportPlacement | None
) -> None:
    result = report_interface.create_from_template("2026-11-10 Incident", placement=placement)

    assert result.is_success and result.data is not None
    assert result.data.vendor_id == CREATED_ID


def test_a_placement_of_another_system_is_unsupported(report_interface: IncidentReport) -> None:
    slack_placement = ReportPlacement(system=WorkplaceSystem.SLACK, tenant="T0SLACK", vendor_id="C0X", label="Slack")

    result = report_interface.create_from_template("2026-11-10 Incident", placement=slack_placement)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.UNSUPPORTED_OPERATION
