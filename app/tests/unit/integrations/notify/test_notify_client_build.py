"""Tests for ``build_notify_client``, the GC Notify vendor client factory.

The factory is given a real ``NotifySettings`` (``model_construct``, so no configuration files
are needed). The transport is observed through a stand-in for ``httpx.AsyncHTTPTransport`` (the
SDK edge): a recording stand-in reads the resilience settings the client is built with, and a
``httpx.MockTransport`` stand-in answers the requests whose Authorization header the JWT tests
decode with the shared secret. The fresh-token test steps the module's issue-time clock
(``_issued_at``) so two requests carry two different ``iat`` claims. Nothing reaches the network.
"""

import socket
from collections.abc import Iterator
from typing import Any

import httpx
import jwt
import pytest
from pydantic import SecretStr

from integrations.notify import client as notify_client
from integrations.notify.client import build_notify_client
from integrations.notify.settings import NotifySettings, NotifyTenant

pytestmark = pytest.mark.unit

API_URL = "https://notify.example.test"
CLIENT_ID = "sre-client-0001"
SECRET = "notify-secret-0001-with-enough-length"


def _settings(
    *,
    tenant: NotifyTenant | None = NotifyTenant(api_url=API_URL),
    timeout_seconds: float = 60.0,
    connect_retries: int = 2,
) -> NotifySettings:
    return NotifySettings.model_construct(
        tenant=tenant,
        sre_user_name=SecretStr(CLIENT_ID if tenant else ""),
        sre_client_secret=SecretStr(SECRET if tenant else ""),
        timeout_seconds=timeout_seconds,
        connect_retries=connect_retries,
    )


@pytest.fixture
def recorded_transports(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    built: list[dict[str, Any]] = []
    real_transport = httpx.AsyncHTTPTransport

    def recording_transport(**kwargs: Any) -> httpx.AsyncHTTPTransport:
        built.append(kwargs)
        return real_transport(**kwargs)

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", recording_transport)
    return built


@pytest.fixture
def answered(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[httpx.Request]]:
    """Every transport the factory builds answers 201 and records the request it received."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json={"result": "ok"})

    def mock_transport(**_: Any) -> httpx.MockTransport:
        return httpx.MockTransport(handler)

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", mock_transport)
    yield requests


def _bearer(request: httpx.Request) -> str:
    scheme, _, token = request.headers["Authorization"].partition(" ")
    assert scheme == "Bearer"
    return token


def test_the_client_targets_the_tenant_host() -> None:
    client = build_notify_client(_settings())

    assert isinstance(client, httpx.AsyncClient)
    assert str(client.base_url).rstrip("/") == API_URL


def test_the_timeout_and_connect_retries_come_from_the_slice(recorded_transports: list[dict[str, Any]]) -> None:
    """The retry policy is set once at construction beside the per-attempt timeout (outbound-clients.md)."""
    client = build_notify_client(_settings(timeout_seconds=12.0, connect_retries=3))

    assert recorded_transports == [{"retries": 3}]
    assert client.timeout == httpx.Timeout(12.0)


def test_a_caller_owning_durable_retry_overrides_the_timeout_and_retries(
    recorded_transports: list[dict[str, Any]],
) -> None:
    """A caller with its own deadline and retry point passes both; the slice values are not used."""
    client = build_notify_client(_settings(timeout_seconds=60.0, connect_retries=2), timeout_seconds=5.0, connect_retries=0)

    assert recorded_transports == [{"retries": 0}]
    assert client.timeout == httpx.Timeout(5.0)


def test_a_missing_tenant_is_a_programming_error() -> None:
    """Consumers check the tenant first; reaching the factory without one is a bug, not an outcome."""
    with pytest.raises(ValueError, match="not configured"):
        build_notify_client(_settings(tenant=None))


def test_building_the_client_opens_no_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    connects: list[Any] = []

    def refuse(self: socket.socket, address: Any) -> None:
        connects.append(address)
        raise AssertionError("the factory opened a connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)

    build_notify_client(_settings())

    assert connects == []


async def test_each_request_carries_an_hs256_jwt_issued_to_the_sre_client(answered: list[httpx.Request]) -> None:
    async with build_notify_client(_settings()) as client:
        await client.post("/sre-tools/api-key-revoke", json={})

    token = _bearer(answered[0])
    assert jwt.get_unverified_header(token) == {"alg": "HS256", "typ": "JWT"}
    claims = jwt.decode(token, SECRET, algorithms=["HS256"])
    assert claims["iss"] == CLIENT_ID
    assert isinstance(claims["iat"], int)


async def test_a_token_signed_with_another_secret_does_not_verify(answered: list[httpx.Request]) -> None:
    async with build_notify_client(_settings()) as client:
        await client.post("/sre-tools/api-key-revoke", json={})

    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(_bearer(answered[0]), "another-secret-of-enough-length-000", algorithms=["HS256"])


async def test_every_request_gets_a_fresh_token(monkeypatch: pytest.MonkeyPatch, answered: list[httpx.Request]) -> None:
    """GC Notify accepts a token only within 30 s of its iat, so a long-lived client signs per request."""
    issued_at = [1_800_000_000.0, 1_800_000_045.0]
    monkeypatch.setattr(notify_client, "_issued_at", lambda: issued_at.pop(0))

    async with build_notify_client(_settings()) as client:
        await client.post("/sre-tools/api-key-revoke", json={})
        await client.post("/sre-tools/api-key-revoke", json={})

    issued = [jwt.decode(_bearer(r), SECRET, algorithms=["HS256"], options={"verify_iat": False})["iat"] for r in answered]
    assert issued == [1_800_000_000, 1_800_000_045]


async def test_a_trailing_slash_on_the_host_is_tolerated(answered: list[httpx.Request]) -> None:
    async with build_notify_client(_settings(tenant=NotifyTenant(api_url=f"{API_URL}/"))) as client:
        await client.post("/sre-tools/api-key-revoke", json={})

    assert str(answered[0].url) == f"{API_URL}/sre-tools/api-key-revoke"
