"""The incident list projection returns classified results for expected failures.

The Sheets service is replaced at the gateway factory by a stand-in whose
requests raise the failure under test, and the settings at their getters.
Statuses follow ``classify_google_error``; a parse-range 400 means the sheet has
no ``Sheet1`` tab and is NOT_FOUND with RANGE_NOT_FOUND; an error no classifier
knows propagates. A missing sheet id or Google tenant refuses before any
request, a conversation of another chat system is unsupported, and no log line
carries the sheet id.
"""

import dataclasses
from collections.abc import Callable
from typing import Any

import pytest
from googleapiclient.errors import HttpError
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.google_sheets import GoogleSheetsIncidentListProjection
from features.incident.core.domain import ConversationReference, Incident
from integrations.google_workspace.client import GoogleCredentialsRefused
from tests.factories.incident_list_sheet import SHEET_ID, FakeSheetsService, install_sheet, listed_incident

pytestmark = pytest.mark.unit

type Call = Callable[[GoogleSheetsIncidentListProjection, Incident], Any]

CALLS: dict[str, Call] = {
    "append_row": lambda projection, incident: projection.append_row(incident),
    "update_status": lambda projection, incident: projection.update_status(incident, IncidentStatus.CLOSED),
}


def _http_error(status: int, retry_after: str | None = None, content: bytes = b"{}") -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            if retry_after is not None:
                self["retry-after"] = retry_after
            self.status = status
            self.reason = "boom"

    return HttpError(resp=FakeResp(), content=content)


class _FailingSheet(FakeSheetsService):
    def __init__(self, failure: Exception) -> None:
        super().__init__()
        self._failure = failure

    def get(self, **kwargs: Any) -> Any:
        raise self._failure


@pytest.fixture(params=sorted(CALLS))
def call(request: pytest.FixtureRequest) -> Call:
    return CALLS[request.param]


async def test_rate_limit_is_transient_with_retry_after(monkeypatch: pytest.MonkeyPatch, call: Call) -> None:
    """A 429 tells the caller to retry later, carrying Sheets' Retry-After."""
    install_sheet(monkeypatch, _FailingSheet(_http_error(429, retry_after="7")))

    result: OperationResult[None] = await call(GoogleSheetsIncidentListProjection(), listed_incident())

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "429"
    assert result.retry_after == 7


async def test_forbidden_is_unauthorized(monkeypatch: pytest.MonkeyPatch, call: Call) -> None:
    """A 403 is the bot lacking access to the sheet: unauthorized."""
    install_sheet(monkeypatch, _FailingSheet(_http_error(403)))

    result = await call(GoogleSheetsIncidentListProjection(), listed_incident())

    assert result.status is OperationStatus.UNAUTHORIZED
    assert result.error_code == "403"


async def test_refused_credentials_are_unauthorized_with_the_cause(monkeypatch: pytest.MonkeyPatch, call: Call) -> None:
    """The gateway refusing the token request is unauthorized, carrying the refusal's cause."""
    install_sheet(monkeypatch, _FailingSheet(GoogleCredentialsRefused("unauthorized_client")))

    result = await call(GoogleSheetsIncidentListProjection(), listed_incident())

    assert result.status is OperationStatus.UNAUTHORIZED
    assert result.error_code == "unauthorized_client"


async def test_unparsable_range_is_not_found(monkeypatch: pytest.MonkeyPatch, call: Call) -> None:
    """A 400 'Unable to parse range' means the Sheet1 tab is gone: NOT_FOUND, RANGE_NOT_FOUND."""
    error = _http_error(400, content=b'{"error": {"message": "Unable to parse range: Sheet1!E:F"}}')
    install_sheet(monkeypatch, _FailingSheet(error))

    result = await call(GoogleSheetsIncidentListProjection(), listed_incident())

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == ErrorCode.RANGE_NOT_FOUND


async def test_other_bad_request_propagates(monkeypatch: pytest.MonkeyPatch, call: Call) -> None:
    """A 400 that is not a missing range is a bug, not a platform failure: it raises."""
    install_sheet(monkeypatch, _FailingSheet(_http_error(400)))

    with pytest.raises(HttpError):
        await call(GoogleSheetsIncidentListProjection(), listed_incident())


async def test_unknown_error_propagates(monkeypatch: pytest.MonkeyPatch, call: Call) -> None:
    """An exception no classifier knows raises."""
    install_sheet(monkeypatch, _FailingSheet(RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        await call(GoogleSheetsIncidentListProjection(), listed_incident())


@pytest.mark.parametrize(
    ("sheet_id", "google_tenant", "named"), [("", True, "list_sheet_id"), (SHEET_ID, False, "google_workspace.tenant")]
)
async def test_missing_configuration_refuses_before_any_request(
    monkeypatch: pytest.MonkeyPatch, call: Call, sheet_id: str, google_tenant: bool, named: str
) -> None:
    """Without a sheet id or a Google tenant nothing is built or requested; the message names the setting."""
    factory = install_sheet(monkeypatch, FakeSheetsService(), sheet_id=sheet_id, google_tenant=google_tenant)

    result = await call(GoogleSheetsIncidentListProjection(), listed_incident())

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED
    assert result.message is not None and named in result.message
    factory.assert_not_called()


async def test_conversation_of_another_chat_system_is_unsupported(monkeypatch: pytest.MonkeyPatch, call: Call) -> None:
    """Only a Slack channel can be linked in the sheet; any other system is refused before a request."""
    factory = install_sheet(monkeypatch, FakeSheetsService())
    incident = dataclasses.replace(
        listed_incident(), conversation=ConversationReference(system=WorkplaceSystem.GOOGLE, tenant="C0", vendor_id="spaces/x")
    )

    result = await call(GoogleSheetsIncidentListProjection(), incident)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.UNSUPPORTED_OPERATION
    factory.assert_not_called()


async def test_failure_log_never_carries_the_sheet_id_or_row_text(monkeypatch: pytest.MonkeyPatch, call: Call) -> None:
    """The warning names the operation and the classified error only."""
    install_sheet(monkeypatch, _FailingSheet(_http_error(429)))

    with capture_logs() as logs:
        await call(GoogleSheetsIncidentListProjection(), listed_incident())

    assert logs
    assert SHEET_ID not in repr(logs)
    assert "Database outage" not in repr(logs)
