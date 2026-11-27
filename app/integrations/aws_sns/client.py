"""The SNS HTTP client factory and its error classifier (decisions/outbound-clients.md).

The client never follows a redirect, so a fetch reaches only the SNS host the caller checked
(OWASP SSRF Prevention). Its retry policy is set here, once: the transport retries a
connection that never opened, so a sent request is never repeated, beside a per-attempt
timeout. No network I/O at construction; the caller manages the client's lifecycle.
"""

import httpx

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus


def build_sns_http_client(*, timeout_seconds: float, connect_retries: int) -> httpx.AsyncClient:
    """Build the client for SNS certificate fetches and subscription confirmations."""
    return httpx.AsyncClient(
        timeout=timeout_seconds,
        follow_redirects=False,
        transport=httpx.AsyncHTTPTransport(retries=connect_retries),
    )


def classify_sns_http_error(exc: Exception) -> tuple[OperationStatus, str | None, int | None]:
    """Classify an httpx failure from an SNS host; propagate unknown exceptions.

    A 429 or 5xx is transient, with the 429's Retry-After seconds when it gives them; a
    redirect or another 4xx is permanent.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 429:
            retry_after = exc.response.headers.get("retry-after", "")
            return OperationStatus.TRANSIENT_ERROR, ErrorCode.RATE_LIMITED, int(retry_after) if retry_after.isdigit() else None
        if status_code >= 500:
            return OperationStatus.TRANSIENT_ERROR, ErrorCode.CONNECTION_ERROR, None
        return OperationStatus.PERMANENT_ERROR, ErrorCode.INVALID_RESPONSE, None
    if isinstance(exc, httpx.TimeoutException):
        return OperationStatus.TRANSIENT_ERROR, ErrorCode.TIMEOUT, None
    if isinstance(exc, httpx.TransportError):
        return OperationStatus.TRANSIENT_ERROR, ErrorCode.CONNECTION_ERROR, None
    raise exc
