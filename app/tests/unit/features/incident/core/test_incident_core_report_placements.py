"""Report placements: where a new report is filed, and how a failed listing is reported.

The Google adapter runs over a stubbed Drive service (the gateway factory is
replaced in the integrations client) with the incident folder configured; the
fake records the folder each report was filed in. The tests assert the folder a
copy is filed in, that a Drive failure is a classified result rather than an
empty list (the legacy helper's behaviour), and the placement value's rules.
"""

from collections.abc import Iterator
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
from features.incident.core.api import ReportPlacement

pytestmark = pytest.mark.unit

TENANT = "C0GOOGLE"
FOLDER_ID = "F0INCIDENTS"
TEMPLATE_ID = "T0TEMPLATE"
APPS = ReportPlacement(system=WorkplaceSystem.GOOGLE, tenant=TENANT, vendor_id="F0APPS", label="Apps")


def _http_error(status: int) -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = "boom"

    return HttpError(resp=cast(Any, FakeResp()), content=b"{}")


@pytest.fixture
def drive(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    service = MagicMock()
    service.files.return_value.copy.return_value.execute.return_value = {"id": "D0NEW", "name": "report"}
    service.files.return_value.list_next.return_value = None
    monkeypatch.setattr(google_docs.google_workspace_client, "get_drive_service", lambda scopes: service)
    monkeypatch.setattr(
        google_docs, "get_google_workspace_settings", lambda: SimpleNamespace(tenant=SimpleNamespace(customer_id=TENANT))
    )
    return service


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(
        google_docs,
        "get_incident_core_settings",
        lambda: IncidentCoreSettings(folder_id=FOLDER_ID, report_template_id=TEMPLATE_ID),
    )
    yield


@pytest.mark.usefixtures("configured")
@pytest.mark.parametrize(("placement", "parent"), [(None, FOLDER_ID), (APPS, "F0APPS")])
def test_the_google_copy_is_filed_in_the_placement_or_the_incident_folder(
    drive: MagicMock, placement: ReportPlacement | None, parent: str
) -> None:
    result = google_docs.GoogleDocsIncidentReport().create_from_template("2026-11-10 Incident", placement=placement)

    assert result.is_success
    body = drive.files.return_value.copy.call_args.kwargs["body"]
    assert body["parents"] == [parent]


@pytest.mark.parametrize(("placement", "folder"), [(None, FOLDER_ID), (APPS, "F0APPS")])
def test_the_fake_files_the_report_in_the_placement_or_the_incident_folder(
    placement: ReportPlacement | None, folder: str
) -> None:
    fake = InMemoryIncidentReport(tenant=TENANT, folder_id=FOLDER_ID, report_template_id=TEMPLATE_ID)

    result = fake.create_from_template("2026-11-10 Incident", placement=placement)

    assert result.data is not None
    assert fake.filed_in(result.data) == folder


@pytest.mark.usefixtures("configured")
def test_a_failed_drive_listing_is_a_classified_result_not_an_empty_list(drive: MagicMock) -> None:
    drive.files.return_value.list.return_value.execute.side_effect = _http_error(503)

    result = google_docs.GoogleDocsIncidentReport().list_placements()

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.data is None


def test_placements_without_an_incident_folder_are_not_configured(drive: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(google_docs, "get_incident_core_settings", lambda: IncidentCoreSettings(folder_id=""))

    result = google_docs.GoogleDocsIncidentReport().list_placements()

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED
    drive.files.return_value.list.assert_not_called()


def test_the_fake_without_an_incident_folder_is_not_configured() -> None:
    result = InMemoryIncidentReport(folder_id="").list_placements()

    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED


def test_a_placement_needs_a_label() -> None:
    with pytest.raises(ValueError, match="label"):
        ReportPlacement(system=WorkplaceSystem.GOOGLE, tenant=TENANT, vendor_id="F0APPS", label=" ")
