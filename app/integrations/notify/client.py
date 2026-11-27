"""GC Notify vendor client: a JWT-authenticated async httpx client factory and its error classifier.

The key revocation lives with its consumer (decisions/outbound-clients.md): today the legacy SNS
``api_key_detected`` pattern.
"""

import json
import time
from collections.abc import Generator

import httpx
import jwt

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from integrations.notify.settings import NotifySettings, get_notify_settings


def _issued_at() -> int:
    """The ``iat`` claim: the current time in epoch seconds (UTC)."""
    return int(time.time())


class _NotifyJwtAuth(httpx.Auth):
    """Sign every request with a fresh HS256 JWT issued to the SRE client.

    GC Notify accepts a token only while its ``iat`` is within 30 seconds of the server's clock,
    so a token fixed in the client's headers would expire while the client lives; httpx runs this
    flow once per request (https://www.python-httpx.org/advanced/authentication/).
    """

    def __init__(self, client_id: str, secret: str) -> None:
        self._client_id = client_id
        self._secret = secret

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        claims = {"iss": self._client_id, "iat": _issued_at()}
        token = jwt.encode(claims, self._secret, algorithm="HS256", headers={"typ": "JWT"})
        request.headers["Authorization"] = f"Bearer {token}"
        yield request


def build_notify_client(
    settings: NotifySettings | None = None,
    *,
    timeout_seconds: float | None = None,
    connect_retries: int | None = None,
) -> httpx.AsyncClient:
    """Build a JWT-authenticated httpx client for the tenant's GC Notify API.

    The retry policy is set here, once: the transport retries a connection that never opened
    ([notify] connect_retries), so a sent request is never repeated, beside the per-attempt
    timeout ([notify] timeout_seconds). A caller that owns durable retry passes its own
    ``timeout_seconds`` and ``connect_retries``; every other caller keeps the configured values.
    The caller checks the tenant first and manages the client's lifecycle (use it as an async
    context manager). No network I/O at construction.
    """
    settings = settings or get_notify_settings()
    if settings.tenant is None:
        raise ValueError("Notify is not configured: [notify.tenant] is unset")
    return httpx.AsyncClient(
        base_url=settings.tenant.api_url,
        auth=_NotifyJwtAuth(settings.sre_user_name.get_secret_value(), settings.sre_client_secret.get_secret_value()),
        timeout=settings.timeout_seconds if timeout_seconds is None else timeout_seconds,
        transport=httpx.AsyncHTTPTransport(retries=settings.connect_retries if connect_retries is None else connect_retries),
    )


def classify_notify_error(exc: Exception) -> tuple[OperationStatus, str | None, int | None]:
    """Classify expected httpx and body-parse failures from the GC Notify API; propagate unknown exceptions.

    ``retry_after`` is the 429 response's Retry-After delay in seconds, or ``None`` when the header
    is absent or not a number of seconds.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 401:
            return OperationStatus.UNAUTHORIZED, ErrorCode.UNAUTHENTICATED, None
        if status_code == 403:
            return OperationStatus.UNAUTHORIZED, ErrorCode.FORBIDDEN, None
        if status_code == 404:
            return OperationStatus.NOT_FOUND, ErrorCode.NOT_FOUND, None
        if status_code == 429:
            return OperationStatus.TRANSIENT_ERROR, ErrorCode.RATE_LIMITED, _retry_after(exc.response)
        if 500 <= status_code < 600:
            return OperationStatus.TRANSIENT_ERROR, ErrorCode.SERVER_ERROR, None
        return OperationStatus.PERMANENT_ERROR, ErrorCode.HTTP_ERROR, None
    if isinstance(exc, httpx.TimeoutException):
        return OperationStatus.TRANSIENT_ERROR, ErrorCode.TIMEOUT, None
    if isinstance(exc, httpx.HTTPError):
        return OperationStatus.TRANSIENT_ERROR, ErrorCode.CONNECTION_ERROR, None
    if isinstance(exc, json.JSONDecodeError):
        return OperationStatus.PERMANENT_ERROR, ErrorCode.INVALID_RESPONSE, None
    raise exc


def _retry_after(response: httpx.Response) -> int | None:
    """Return the Retry-After delay in seconds, or ``None`` when absent or an HTTP-date."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
