"""Unit tests for the SNS adapter: certificate fetches and subscription confirmations.

The adapter runs on a real ``httpx.AsyncClient`` over ``httpx.MockTransport``, so the requests
it makes are recorded and its responses scripted; the clock is a counter the test moves.
Assertions check what was requested and what the port returned.
"""

import httpx
import pytest

from capabilities.webhooks.adapters.aws_sns import AwsSnsHttp
from contracts.operations import OperationStatus
from integrations.aws_sns import build_sns_http_client
from tests.unit.capabilities.webhooks.sns_signing import CERT_URL, SUBSCRIBE_URL

pytestmark = pytest.mark.unit


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _port(handler, clock: _Clock | None = None, size: int = 2) -> tuple[AwsSnsHttp, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(record), follow_redirects=False)
    return AwsSnsHttp(client, cache_ttl_seconds=60, cache_size=size, clock=clock or _Clock()), seen


async def test_a_certificate_is_fetched_once_and_served_from_the_cache_while_fresh() -> None:
    clock = _Clock()
    port, seen = _port(lambda request: httpx.Response(200, content=b"PEM"), clock)

    first = await port.certificate(CERT_URL)
    second = await port.certificate(CERT_URL)
    clock.now = 61
    third = await port.certificate(CERT_URL)

    assert (first.data, second.data, third.data) == (b"PEM", b"PEM", b"PEM")
    assert len(seen) == 2


async def test_the_cache_keeps_at_most_its_size() -> None:
    port, seen = _port(lambda request: httpx.Response(200, content=b"PEM"), size=1)
    other = CERT_URL.replace("0000", "1111")

    await port.certificate(CERT_URL)
    await port.certificate(other)
    await port.certificate(CERT_URL)

    assert len(seen) == 3


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.com/cert.pem",
        "https://sns.ca-central-1.amazonaws.com/cert.txt",
        "https://user@sns.ca-central-1.amazonaws.com/cert.pem",
        "https://sns.ca-central-1.amazonaws.com:8443/cert.pem",
    ],
)
async def test_a_url_off_an_sns_certificate_path_is_never_requested(url: str) -> None:
    port, seen = _port(lambda request: httpx.Response(200, content=b"PEM"))

    result = await port.certificate(url)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert seen == []


async def test_a_redirect_is_not_followed() -> None:
    port, seen = _port(lambda request: httpx.Response(302, headers={"location": "https://evil.example.com/cert.pem"}))

    result = await port.certificate(CERT_URL)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert [request.url.host for request in seen] == ["sns.ca-central-1.amazonaws.com"]


@pytest.mark.parametrize(
    ("response", "status"),
    [
        (httpx.Response(503), OperationStatus.TRANSIENT_ERROR),
        (httpx.Response(429, headers={"retry-after": "7"}), OperationStatus.TRANSIENT_ERROR),
        (httpx.Response(404), OperationStatus.PERMANENT_ERROR),
    ],
)
async def test_a_failed_fetch_is_classified(response: httpx.Response, status: OperationStatus) -> None:
    port, _ = _port(lambda request: response)

    assert (await port.certificate(CERT_URL)).status is status


async def test_a_timeout_is_transient() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    port, _ = _port(timeout)

    assert (await port.certificate(CERT_URL)).status is OperationStatus.TRANSIENT_ERROR


async def test_a_subscription_is_confirmed_by_one_get_to_its_sns_url() -> None:
    port, seen = _port(lambda request: httpx.Response(200, content=b"<ConfirmSubscriptionResponse/>"))

    result = await port.confirm(SUBSCRIBE_URL)

    assert result.is_success
    assert [(request.method, str(request.url)) for request in seen] == [("GET", SUBSCRIBE_URL)]


async def test_a_subscribe_url_off_an_sns_host_is_never_requested() -> None:
    port, seen = _port(lambda request: httpx.Response(200))

    result = await port.confirm("https://evil.example.com/?Action=ConfirmSubscription")

    assert result.status is OperationStatus.PERMANENT_ERROR and seen == []


def test_the_factory_client_never_follows_redirects() -> None:
    client = build_sns_http_client(timeout_seconds=3.0, connect_retries=2)

    assert client.follow_redirects is False
    assert client.timeout.read == 3.0
