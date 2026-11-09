"""OpenAI vendor client: authenticated client factory and error classification.

``build_openai_client`` builds the authenticated client with its resilience settings,
and ``classify_openai_error`` maps the expected httpx failures onto the outbound-client
contract's (status, error_code, retry_after) tuple (decisions/outbound-clients.md). The
module holds no business logic; the adapter calling the API wraps the call in
``try/except`` and classifies.
"""

import httpx

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from integrations.openai.settings import OpenAISettings, get_openai_settings


def build_openai_client(settings: OpenAISettings | None = None) -> httpx.AsyncClient:
    """Build an authenticated httpx client for the OpenAI REST API.

    The retry policy is set here, once: the transport retries a connection that never
    opened ([openai] connect_retries; httpcore retries only ``ConnectError`` and
    ``ConnectTimeout``, with backoff), so a completion that reached the endpoint is never
    re-sent. The caller manages the client's lifecycle (use it as an async context manager).
    """
    settings = settings or get_openai_settings()
    return httpx.AsyncClient(
        base_url=settings.base_url,
        headers={
            "Authorization": f"Bearer {settings.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        },
        timeout=settings.timeout_seconds,
        transport=httpx.AsyncHTTPTransport(retries=settings.connect_retries),
    )


def classify_openai_error(exc: Exception) -> tuple[OperationStatus, str | None, int | None]:
    """Classify expected httpx failures from the OpenAI API; propagate unknown exceptions.

    ``retry_after`` is the 429 response's Retry-After delay in seconds, or ``None`` when
    the header is absent or not a number of seconds.
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
