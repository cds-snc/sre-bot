"""Reading an incident's roles: the record's, else the legacy report's Drive properties.

``read_incident_roles`` runs over the in-memory legacy roles reader, which stands in for
``GoogleDriveLegacyRolesReader``; the adapter is tested over a fake Drive service at the Google client edge,
asserting the property mapping, the blank and missing cases, the classified failures and that
the one blocking call runs in one worker thread.
"""

import threading
from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.adapters.in_memory import InMemoryLegacyRolesReader
from features.incident.core.adapters.legacy_roles import GoogleDriveLegacyRolesReader
from features.incident.core.api import ReportReference, read_incident_roles
from integrations.google_workspace import client as google_workspace_client
from tests.factories.incident import GOOGLE_TENANT, incident_on

pytestmark = pytest.mark.unit

GOOGLE_REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="F0REPORT")
OTHER_REPORT = ReportReference(system=WorkplaceSystem.SLACK, tenant="T0SLACK", vendor_id="canvas-1")
NO_ROLES = dict.fromkeys(IncidentRole)
LEGACY = {IncidentRole.INCIDENT_COMMANDER: "U0OLDIC", IncidentRole.OPERATIONS_LEAD: "U0OLDOL"}


def _incident(report: ReportReference | None = GOOGLE_REPORT, **roles: str) -> Any:
    return replace(incident_on("C0INCIDENT", "inc-1"), report=report, **roles)


async def test_the_records_roles_win_and_the_report_is_not_read() -> None:
    legacy = InMemoryLegacyRolesReader()
    legacy.seed(GOOGLE_REPORT, LEGACY)

    roles = await read_incident_roles(_incident(policy_lead="U0POLICY"), legacy)

    assert roles == {**NO_ROLES, IncidentRole.POLICY_LEAD: "U0POLICY"}
    assert legacy.reads == []


async def test_an_incident_without_roles_reads_the_commander_and_lead_from_its_google_report() -> None:
    legacy = InMemoryLegacyRolesReader()
    legacy.seed(GOOGLE_REPORT, LEGACY)

    roles = await read_incident_roles(_incident(), legacy)

    assert roles == {**NO_ROLES, **LEGACY}
    assert legacy.reads == [GOOGLE_REPORT]


@pytest.mark.parametrize("report", [None, OTHER_REPORT])
async def test_an_incident_without_a_google_report_reads_nothing(report: ReportReference | None) -> None:
    legacy = InMemoryLegacyRolesReader()

    roles = await read_incident_roles(_incident(report), legacy)

    assert roles == NO_ROLES
    assert legacy.reads == []


async def test_a_failed_legacy_read_is_logged_and_yields_no_roles() -> None:
    legacy = InMemoryLegacyRolesReader()

    with capture_logs() as logs:
        roles = await read_incident_roles(_incident(), legacy)

    assert roles == NO_ROLES
    [event] = [entry for entry in logs if entry["event"] == "incident_legacy_roles_read_failed"]
    assert (event["incident_id"], event["operation_status"]) == ("inc-1", "not_found")


def _http_error(status: int) -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = "boom"

    return HttpError(resp=FakeResp(), content=b"{}")


class _Drive:
    """A Drive service whose ``files().get()`` answers ``metadata`` (or raises ``error``) and records each request."""

    def __init__(self, metadata: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.requests: list[dict[str, Any]] = []
        self.threads: list[int] = []
        self.service = MagicMock()
        self.service.files.return_value.get.side_effect = self._get
        self._metadata = metadata or {}
        self._error = error

    def _get(self, **kwargs: Any) -> MagicMock:
        self.requests.append(kwargs)
        request = MagicMock()
        request.execute.side_effect = self._execute
        return request

    def _execute(self) -> dict[str, Any]:
        self.threads.append(threading.get_ident())
        if self._error is not None:
            raise self._error
        return self._metadata


def _on_drive(monkeypatch: pytest.MonkeyPatch, drive: _Drive) -> None:
    monkeypatch.setattr(google_workspace_client, "get_drive_service", lambda **_: drive.service)


async def test_the_drive_adapter_maps_the_report_properties_to_the_commander_and_lead(monkeypatch: pytest.MonkeyPatch) -> None:
    drive = _Drive({"appProperties": {"ic_id": "U0OLDIC", "ol_id": "U0OLDOL", "other": "x"}})
    _on_drive(monkeypatch, drive)

    result = await GoogleDriveLegacyRolesReader().read(GOOGLE_REPORT)

    assert result.data == LEGACY
    assert [(request["fileId"], request["fields"]) for request in drive.requests] == [("F0REPORT", "appProperties")]


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({}, {}),
        ({"appProperties": {"ic_id": "  ", "ol_id": "U0OLDOL"}}, {IncidentRole.OPERATIONS_LEAD: "U0OLDOL"}),
        ({"appProperties": {"ic_id": "U0OLDIC"}}, {IncidentRole.INCIDENT_COMMANDER: "U0OLDIC"}),
    ],
)
async def test_the_drive_adapter_leaves_out_a_blank_or_missing_property(
    monkeypatch: pytest.MonkeyPatch, metadata: dict[str, Any], expected: dict[IncidentRole, str]
) -> None:
    _on_drive(monkeypatch, _Drive(metadata))

    result = await GoogleDriveLegacyRolesReader().read(GOOGLE_REPORT)

    assert result.is_success
    assert result.data == expected


async def test_the_drive_adapter_classifies_a_missing_file_as_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    _on_drive(monkeypatch, _Drive(error=_http_error(404)))

    result = await GoogleDriveLegacyRolesReader().read(GOOGLE_REPORT)

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == "404"


async def test_the_drive_adapter_refuses_a_report_of_another_system_without_a_call(monkeypatch: pytest.MonkeyPatch) -> None:
    drive = _Drive()
    _on_drive(monkeypatch, drive)

    result = await GoogleDriveLegacyRolesReader().read(OTHER_REPORT)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.UNSUPPORTED_OPERATION
    assert drive.requests == []


async def test_the_drive_adapter_runs_the_blocking_call_in_one_worker_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    drive = _Drive()
    _on_drive(monkeypatch, drive)

    result: OperationResult[Any] = await GoogleDriveLegacyRolesReader().read(GOOGLE_REPORT)

    assert result.is_success
    assert len(drive.threads) == 1
    assert drive.threads[0] != threading.get_ident()
