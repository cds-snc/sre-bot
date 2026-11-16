"""Unit tests for the Opsgenie schedule source.

The source is built with injected settings (a real ``OpsGenieSettings`` from ``model_construct``)
and a client factory returning an ``httpx.AsyncClient`` over an ``httpx.MockTransport``, the HTTP
edge, with a fixed clock. Assertions are on the results (status, code, data), the request paths
and counts, and that unexpected exceptions propagate.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from capabilities.oncall.adapters.opsgenie import OpsgenieSource
from capabilities.oncall.domain import OPSGENIE, OnCallPerson, ScheduleReference
from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from integrations.opsgenie.settings import OpsGenieSettings, OpsGenieTenant

pytestmark = pytest.mark.unit

API_URL = "https://api.opsgenie.com"
NOW = datetime(2026, 11, 16, 12, tzinfo=UTC)
REFERENCE = ScheduleReference(OPSGENIE, "sched-1")


def _settings(configured: bool = True) -> OpsGenieSettings:
    return OpsGenieSettings.model_construct(
        tenant=OpsGenieTenant(api_url=API_URL) if configured else None,
        integrations_key=SecretStr("genie-key" if configured else ""),
        timeout_seconds=5.0,
        connect_retries=0,
    )


def _person(email: str) -> OnCallPerson:
    return OnCallPerson(email=email, account=None)


def _on_calls(*names: Any) -> dict[str, Any]:
    return {"data": {"onCallParticipants": [{"name": name} for name in names]}}


def _timeline(*rotations: dict[str, Any]) -> dict[str, Any]:
    return {"data": {"finalTimeline": {"rotations": list(rotations)}}}


def _period(start: datetime, recipient: dict[str, Any]) -> dict[str, Any]:
    return {"startDate": start.isoformat(), "recipient": recipient}


class _Edge:
    """Records each request and answers with ``handler``."""

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def build(self, settings: OpsGenieSettings) -> httpx.AsyncClient:
        assert settings.tenant is not None
        return httpx.AsyncClient(base_url=settings.tenant.api_url, transport=httpx.MockTransport(self._answer))

    def _answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)


def _source(edge: _Edge, configured: bool = True) -> OpsgenieSource:
    return OpsgenieSource(settings=lambda: _settings(configured), client_factory=edge.build, clock=lambda: NOW)


def _answering(body: Any) -> _Edge:
    return _Edge(lambda request: httpx.Response(200, json=body))


async def test_one_participant_is_returned_by_email() -> None:
    edge = _answering(_on_calls("a@example.org"))

    result = await _source(edge).on_call_now(REFERENCE)

    assert result.status is OperationStatus.SUCCESS
    assert result.data == (_person("a@example.org"),)
    assert [request.url.path for request in edge.requests] == ["/v2/schedules/sched-1/on-calls"]


async def test_several_participants_are_returned_in_order() -> None:
    result = await _source(_answering(_on_calls("a@example.org", "b@example.org"))).on_call_now(REFERENCE)

    assert result.data == (_person("a@example.org"), _person("b@example.org"))


async def test_a_rotation_reads_the_timeline_and_returns_its_active_user() -> None:
    body = _timeline(
        {"name": "other", "periods": [_period(NOW - timedelta(hours=1), {"type": "user", "name": "o@example.org"})]},
        {"name": "rot-1", "periods": [_period(NOW - timedelta(hours=1), {"type": "user", "name": "r@example.org"})]},
    )
    edge = _answering(body)

    result = await _source(edge).on_call_now(REFERENCE, rotation="rot-1")

    assert result.data == (_person("r@example.org"),)
    assert [request.url.path for request in edge.requests] == ["/v2/schedules/sched-1/timeline"]


@pytest.mark.parametrize(
    "rotations",
    [
        [],
        [{"name": "rot-1", "periods": []}],
        [{"name": "rot-1", "periods": [_period(NOW + timedelta(hours=2), {"type": "user", "name": "late@example.org"})]}],
        [{"name": "rot-1", "periods": [_period(NOW - timedelta(hours=1), {"type": "team", "name": "team"})]}],
        [{"name": "rot-1", "periods": [_period(NOW - timedelta(hours=1), {})]}],
    ],
    ids=["rotation-absent", "no-periods", "starts-in-the-future", "recipient-not-a-user", "no-recipient"],
)
async def test_a_coverage_gap_or_a_non_user_recipient_is_an_empty_success(rotations: list[dict[str, Any]]) -> None:
    result = await _source(_answering(_timeline(*rotations))).on_call_now(REFERENCE, rotation="rot-1")

    assert result.status is OperationStatus.SUCCESS
    assert result.data == ()


@pytest.mark.parametrize(
    ("status_code", "status", "code"),
    [
        (500, OperationStatus.TRANSIENT_ERROR, ErrorCode.SERVER_ERROR),
        (429, OperationStatus.TRANSIENT_ERROR, ErrorCode.RATE_LIMITED),
        (401, OperationStatus.UNAUTHORIZED, ErrorCode.UNAUTHENTICATED),
        (404, OperationStatus.NOT_FOUND, ErrorCode.NOT_FOUND),
    ],
)
async def test_an_http_status_failure_is_classified(status_code: int, status: OperationStatus, code: ErrorCode) -> None:
    result = await _source(_Edge(lambda request: httpx.Response(status_code))).on_call_now(REFERENCE)

    assert (result.status, result.error_code) == (status, code)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (httpx.ReadTimeout("slow"), ErrorCode.TIMEOUT),
        (httpx.ConnectError("refused"), ErrorCode.CONNECTION_ERROR),
    ],
)
async def test_a_transport_failure_is_a_classified_transient_error(error: httpx.HTTPError, code: ErrorCode) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise error

    result = await _source(_Edge(fail)).on_call_now(REFERENCE)

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.error_code == code


async def test_a_body_that_is_not_json_is_invalid_response() -> None:
    result = await _source(_Edge(lambda request: httpx.Response(200, content=b"<html>"))).on_call_now(REFERENCE)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INVALID_RESPONSE


@pytest.mark.parametrize(
    ("body", "rotation"),
    [
        ([], None),
        ({"data": {}}, None),
        ({"data": {"onCallParticipants": [{"id": "no-name"}]}}, None),
        ({"data": {"onCallParticipants": [{"name": 7}]}}, None),
        ({"data": {}}, "rot-1"),
        (_timeline({"name": "rot-1", "periods": "nope"}), "rot-1"),
        (_timeline({"name": "rot-1", "periods": [{"startDate": 5}]}), "rot-1"),
        (_timeline({"name": "rot-1", "periods": [{"startDate": "not a date"}]}), "rot-1"),
        (_timeline({"name": "rot-1", "periods": [_period(NOW - timedelta(hours=1), {"type": "user"})]}), "rot-1"),
    ],
)
async def test_a_body_of_the_wrong_shape_is_invalid_response(body: Any, rotation: str | None) -> None:
    result = await _source(_answering(body)).on_call_now(REFERENCE, rotation=rotation)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INVALID_RESPONSE


async def test_without_a_tenant_no_request_is_made() -> None:
    edge = _answering(_on_calls("a@example.org"))

    result = await _source(edge, configured=False).on_call_now(REFERENCE)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED
    assert edge.requests == []


async def test_an_unexpected_exception_propagates() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await _source(_Edge(fail)).on_call_now(REFERENCE)


async def test_get_schedule_is_unsupported() -> None:
    edge = _answering({})

    result = await _source(edge).get_schedule(REFERENCE)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.UNSUPPORTED_OPERATION
    assert edge.requests == []


async def test_list_schedules_is_an_empty_success() -> None:
    result = await _source(_answering({})).list_schedules()

    assert result.status is OperationStatus.SUCCESS
    assert result.data == ()
