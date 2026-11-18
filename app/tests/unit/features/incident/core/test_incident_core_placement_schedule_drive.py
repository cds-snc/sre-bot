"""The interim placement schedule lookup: a report placement's Drive folder ``genie_schedule`` property.

``GoogleDrivePlacementScheduleLookup`` runs over a fake Drive service at the Google
client edge, as the legacy roles reader's test does. Assertions read the returned
``ScheduleReference`` (the on-call capability's own type, so the declare asks
``capabilities.oncall.api`` with it), the absent and blank cases, the classified
failure, the refusal of another system's placement and that the one blocking call
runs in a worker thread. The in-memory lookup answers the same rules for the
declare tests. Tolerated until TASK-165.1 moves the schedule into the product
catalogue (decisions/incident-management.md).
"""

import threading
from typing import Any
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from capabilities.oncall.api import OPSGENIE, ScheduleReference
from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.in_memory import InMemoryPlacementScheduleLookup
from features.incident.core.adapters.legacy_schedule import GoogleDrivePlacementScheduleLookup
from features.incident.core.api import PlacementScheduleLookup, ReportPlacement
from integrations.google_workspace import client as google_workspace_client
from tests.factories.incident import GOOGLE_TENANT

pytestmark = pytest.mark.unit

PLACEMENT = ReportPlacement(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="F0PAYMENTS", label="Payments")
OTHER = ReportPlacement(system=WorkplaceSystem.SLACK, tenant="T0SLACK", vendor_id="X", label="Elsewhere")


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


def test_both_implement_the_protocol() -> None:
    assert isinstance(GoogleDrivePlacementScheduleLookup(), PlacementScheduleLookup)
    assert isinstance(InMemoryPlacementScheduleLookup(), PlacementScheduleLookup)


async def test_the_folders_genie_schedule_is_an_opsgenie_schedule_reference_read_in_a_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drive = _Drive({"appProperties": {"genie_schedule": " sched-payments "}})
    _on_drive(monkeypatch, drive)

    result = await GoogleDrivePlacementScheduleLookup().schedule_for(PLACEMENT)

    assert result.data == ScheduleReference(system=OPSGENIE, id="sched-payments")
    assert drive.requests[0]["fileId"] == "F0PAYMENTS"
    assert drive.threads != [threading.get_ident()]


@pytest.mark.parametrize("metadata", [{}, {"appProperties": {}}, {"appProperties": {"genie_schedule": "  "}}])
async def test_a_folder_without_a_schedule_has_none(monkeypatch: pytest.MonkeyPatch, metadata: dict[str, Any]) -> None:
    _on_drive(monkeypatch, _Drive(metadata))

    result = await GoogleDrivePlacementScheduleLookup().schedule_for(PLACEMENT)

    assert result.is_success
    assert result.data is None


async def test_a_drive_failure_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    _on_drive(monkeypatch, _Drive(error=_http_error(404)))

    result = await GoogleDrivePlacementScheduleLookup().schedule_for(PLACEMENT)

    assert result.status is OperationStatus.NOT_FOUND


async def test_another_systems_placement_is_unsupported_without_a_call(monkeypatch: pytest.MonkeyPatch) -> None:
    drive = _Drive()
    _on_drive(monkeypatch, drive)

    result = await GoogleDrivePlacementScheduleLookup().schedule_for(OTHER)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.UNSUPPORTED_OPERATION
    assert drive.requests == []


async def test_the_in_memory_lookup_answers_its_seeded_schedules_and_none_otherwise() -> None:
    reference = ScheduleReference(system=OPSGENIE, id="sched-payments")
    lookup = InMemoryPlacementScheduleLookup({"F0PAYMENTS": reference})

    assert (await lookup.schedule_for(PLACEMENT)).data == reference
    assert (await lookup.schedule_for(OTHER)).data is None
