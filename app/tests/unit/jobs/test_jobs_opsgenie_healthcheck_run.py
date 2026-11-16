"""Tests for the scheduler's Opsgenie health-check probe.

The probe is called directly (it is sync: one ``asyncio.run`` per check). The HTTP edge is an
``httpx.MockTransport`` behind a stand-in for ``build_opsgenie_client``; the settings are a real
``OpsGenieSettings`` from ``model_construct``. Assertions are on the healthy verdict and the
request path; an unexpected exception propagates to ``integration_healthchecks``' per-check
handler, which reports that integration unhealthy.
"""

from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr

from integrations.opsgenie.settings import OpsGenieSettings, OpsGenieTenant
from jobs import scheduled_tasks

pytestmark = pytest.mark.unit


def _wire(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response], configured: bool = True
) -> list[httpx.Request]:
    requests: list[httpx.Request] = []
    settings = OpsGenieSettings.model_construct(
        tenant=OpsGenieTenant(api_url="https://api.opsgenie.com") if configured else None,
        integrations_key=SecretStr("genie-key" if configured else ""),
        timeout_seconds=5.0,
        connect_retries=0,
    )

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    def build(given: OpsGenieSettings) -> httpx.AsyncClient:
        assert given.tenant is not None
        return httpx.AsyncClient(base_url=given.tenant.api_url, transport=httpx.MockTransport(answer))

    monkeypatch.setattr(scheduled_tasks, "get_opsgenie_settings", lambda: settings)
    monkeypatch.setattr(scheduled_tasks, "build_opsgenie_client", build)
    return requests


def test_a_services_listing_is_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _wire(monkeypatch, lambda request: httpx.Response(200, json={"data": []}))

    assert scheduled_tasks._opsgenie_healthcheck() is True
    assert [r.url.path for r in requests] == ["/v1/services"]


def test_a_body_without_data_is_unhealthy(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, lambda request: httpx.Response(200, json={"message": "nope"}))

    assert scheduled_tasks._opsgenie_healthcheck() is False


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(httpx.Response(401), id="unauthenticated"),
        pytest.param(httpx.Response(503), id="server error"),
        pytest.param(httpx.Response(200, text="<html>"), id="unparseable body"),
    ],
)
def test_a_classified_failure_is_unhealthy(monkeypatch: pytest.MonkeyPatch, response: httpx.Response) -> None:
    _wire(monkeypatch, lambda request: response)

    assert scheduled_tasks._opsgenie_healthcheck() is False


def test_not_configured_is_unhealthy_without_a_request(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _wire(monkeypatch, lambda request: httpx.Response(200, json={"data": []}), configured=False)

    assert scheduled_tasks._opsgenie_healthcheck() is False
    assert requests == []


def test_an_unexpected_exception_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("bug in the transport handler")

    _wire(monkeypatch, broken)

    with pytest.raises(RuntimeError):
        scheduled_tasks._opsgenie_healthcheck()
