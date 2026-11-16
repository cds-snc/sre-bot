"""Unit tests for the Opsgenie on-call schedule adapter.

The adapter is built with injected settings (a real ``OpsGenieSettings`` from
``model_construct``) and a client factory that returns an ``httpx.AsyncClient`` over an
``httpx.MockTransport``, the HTTP edge. Assertions are on the email returned, the
``OnCallSyncError`` raised (with its cause) and the request path, never on logging.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from contracts.operations.codes import ErrorCode
from integrations.opsgenie.settings import OpsGenieSettings, OpsGenieTenant
from packages.oncall_sync.adapters.opsgenie import OpsGenieScheduleProvider
from packages.oncall_sync.ports import OnCallSyncError
from packages.oncall_sync.settings import OnCallRotation

pytestmark = pytest.mark.unit

API_URL = "https://api.opsgenie.com"
NOW = datetime.now(UTC)


def _rotation() -> OnCallRotation:
    return OnCallRotation(
        opsgenie_schedule_id="sched-1",
        opsgenie_rotation_name="rot-1",
        slack_handle="oncall-x",
        slack_name="On-call X",
    )


def _settings(configured: bool = True) -> OpsGenieSettings:
    return OpsGenieSettings.model_construct(
        tenant=OpsGenieTenant(api_url=API_URL) if configured else None,
        integrations_key=SecretStr("genie-key" if configured else ""),
        timeout_seconds=5.0,
        connect_retries=0,
    )


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


def _provider(edge: _Edge, configured: bool = True) -> OpsGenieScheduleProvider:
    return OpsGenieScheduleProvider(settings=lambda: _settings(configured), client_factory=edge.build)


async def test_returns_the_active_user_of_the_named_rotation() -> None:
    edge = _Edge(
        lambda request: httpx.Response(
            200,
            json=_timeline(
                {"name": "other", "periods": [_period(NOW - timedelta(hours=1), {"type": "user", "name": "o@x.ca"})]},
                {"name": "rot-1", "periods": [_period(NOW - timedelta(hours=1), {"type": "user", "name": "a@x.ca"})]},
            ),
        )
    )

    assert await _provider(edge).get_current_on_call_email(_rotation()) == "a@x.ca"
    assert [r.url.path for r in edge.requests] == ["/v2/schedules/sched-1/timeline"]
    assert dict(edge.requests[0].url.params) == {"identifierType": "id", "interval": "1", "intervalUnit": "days"}


@pytest.mark.parametrize(
    "rotations",
    [
        pytest.param([], id="rotation absent"),
        pytest.param([{"name": "rot-1", "periods": []}], id="no periods"),
        pytest.param([{"name": "rot-1"}], id="periods missing"),
        pytest.param(
            [{"name": "rot-1", "periods": [_period(NOW - timedelta(hours=1), {"type": "team", "name": "t"})]}],
            id="team recipient",
        ),
        pytest.param(
            [{"name": "rot-1", "periods": [_period(NOW + timedelta(hours=1), {"type": "user", "name": "a@x.ca"})]}],
            id="coverage gap",
        ),
    ],
)
async def test_returns_none_when_nobody_is_on_call(rotations: list[dict[str, Any]]) -> None:
    edge = _Edge(lambda request: httpx.Response(200, json=_timeline(*rotations)))

    assert await _provider(edge).get_current_on_call_email(_rotation()) is None


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(httpx.Response(500), id="server error"),
        pytest.param(httpx.Response(401), id="unauthenticated"),
        pytest.param(httpx.Response(200, text="<html>"), id="unparseable body"),
    ],
)
async def test_a_classified_failure_raises_oncall_sync_error_with_its_cause(response: httpx.Response) -> None:
    edge = _Edge(lambda request: response)

    with pytest.raises(OnCallSyncError) as excinfo:
        await _provider(edge).get_current_on_call_email(_rotation())

    assert excinfo.value.__cause__ is not None


async def test_a_timeout_raises_oncall_sync_error() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(OnCallSyncError) as excinfo:
        await _provider(_Edge(slow)).get_current_on_call_email(_rotation())

    assert isinstance(excinfo.value.__cause__, httpx.ReadTimeout)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"data": {}}, id="no final timeline"),
        pytest.param(_timeline({"name": "rot-1", "periods": [{"recipient": {"type": "user"}}]}), id="period without start"),
        pytest.param(_timeline({"name": "rot-1", "periods": [_period(NOW, {"type": "user"})]}), id="user without name"),
    ],
)
async def test_an_unexpected_shape_raises_oncall_sync_error(body: dict[str, Any]) -> None:
    edge = _Edge(lambda request: httpx.Response(200, json=body))

    with pytest.raises(OnCallSyncError, match=ErrorCode.INVALID_RESPONSE):
        await _provider(edge).get_current_on_call_email(_rotation())


async def test_not_configured_raises_without_a_request() -> None:
    edge = _Edge(lambda request: httpx.Response(200, json=_timeline()))

    with pytest.raises(OnCallSyncError, match=ErrorCode.CONFIG_NOT_CONFIGURED):
        await _provider(edge, configured=False).get_current_on_call_email(_rotation())

    assert edge.requests == []


async def test_an_unexpected_exception_propagates_unwrapped() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("bug in the transport handler")

    with pytest.raises(RuntimeError):
        await _provider(_Edge(broken)).get_current_on_call_email(_rotation())
