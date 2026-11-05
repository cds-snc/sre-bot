"""A new incident report is copied from the configured template into the configured folder.

The Google Docs adapter reads [incident_core] folder_id and report_template_id
at call time. The Drive service is a stub whose ``files().copy`` call is
inspected, so the test sees which template is copied, where the copy is filed
and that shared drives stay supported. An empty id, or no Google tenant to name
the reference with, refuses with CONFIG_NOT_CONFIGURED naming the missing key
and calls Drive never. A Drive refusal comes back as its classified status.
"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from features.incident.common.settings import IncidentCoreSettings
from features.incident.core.adapters import google_docs

pytestmark = pytest.mark.unit


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
    service.files.return_value.copy.return_value.execute.return_value = {"id": "D0NEW", "name": "Incident"}
    monkeypatch.setattr(google_docs.google_workspace_client, "get_drive_service", lambda scopes: service)
    monkeypatch.setattr(
        google_docs, "get_google_workspace_settings", lambda: SimpleNamespace(tenant=SimpleNamespace(customer_id="C0GOOGLE"))
    )
    return service


def _configure(
    monkeypatch: pytest.MonkeyPatch, *, folder_id: str = "F0INCIDENTS", report_template_id: str = "T0TEMPLATE"
) -> None:
    monkeypatch.setattr(
        google_docs,
        "get_incident_core_settings",
        lambda: IncidentCoreSettings(folder_id=folder_id, report_template_id=report_template_id),
    )


def test_a_new_report_is_a_copy_of_the_template_filed_in_the_configured_folder(
    drive: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)

    result = google_docs.GoogleDocsIncidentReport().create_from_template("2026-11-05 Database outage")

    assert result.is_success and result.data is not None
    assert result.data.vendor_id == "D0NEW"
    drive.files.return_value.copy.assert_called_once_with(
        fileId="T0TEMPLATE",
        body={"name": "2026-11-05 Database outage", "parents": ["F0INCIDENTS"]},
        supportsAllDrives=True,
    )


@pytest.mark.parametrize(
    ("configured", "key"),
    [
        pytest.param({"folder_id": ""}, "incident_core.folder_id", id="folder"),
        pytest.param({"report_template_id": ""}, "incident_core.report_template_id", id="template"),
    ],
)
def test_an_empty_document_id_refuses_naming_the_key_and_calls_no_drive(
    drive: MagicMock, monkeypatch: pytest.MonkeyPatch, configured: dict[str, str], key: str
) -> None:
    _configure(monkeypatch, **configured)

    result = google_docs.GoogleDocsIncidentReport().create_from_template("Incident")

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED
    assert key in (result.message or "")
    drive.files.return_value.copy.assert_not_called()


def test_no_google_tenant_refuses_naming_the_tenant_entry(drive: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(google_docs, "get_google_workspace_settings", lambda: SimpleNamespace(tenant=None))

    result = google_docs.GoogleDocsIncidentReport().create_from_template("Incident")

    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED
    assert "google_workspace.tenant" in (result.message or "")
    drive.files.return_value.copy.assert_not_called()


def test_a_drive_refusal_comes_back_as_its_classified_status(drive: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    drive.files.return_value.copy.return_value.execute.side_effect = _http_error(403)

    result = google_docs.GoogleDocsIncidentReport().create_from_template("Incident")

    assert result.status is OperationStatus.UNAUTHORIZED
    assert result.error_code == "403"
