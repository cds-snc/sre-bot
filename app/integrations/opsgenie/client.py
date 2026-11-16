"""Opsgenie vendor client: an authenticated async httpx client factory and its error classifier.

The on-call reads live with their consumers (decisions/outbound-clients.md): the oncall_sync
schedule adapter, the legacy declare helper in ``modules/incident/on_call.py`` and the
scheduler's health-check probe. Every Opsgenie call is a GET.
"""

import json

import httpx

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from integrations.opsgenie.settings import OpsGenieSettings, get_opsgenie_settings


def build_opsgenie_client(settings: OpsGenieSettings | None = None) -> httpx.AsyncClient:
    """Build an authenticated httpx client for the tenant's regional Opsgenie API.

    The retry policy is set here, once: the transport retries a connection that never opened
    ([opsgenie] connect_retries), so a sent request is never repeated, beside the per-attempt
    timeout ([opsgenie] timeout_seconds). The caller checks the tenant first and manages the
    client's lifecycle (use it as an async context manager). No network I/O at construction.
    """
    settings = settings or get_opsgenie_settings()
    if settings.tenant is None:
        raise ValueError("Opsgenie is not configured: [opsgenie.tenant] is unset")
    return httpx.AsyncClient(
        base_url=settings.tenant.api_url,
        headers={"Authorization": f"GenieKey {settings.integrations_key.get_secret_value()}"},
        timeout=settings.timeout_seconds,
        transport=httpx.AsyncHTTPTransport(retries=settings.connect_retries),
    )


def classify_opsgenie_error(exc: Exception) -> tuple[OperationStatus, str | None, int | None]:
    """Classify expected httpx and body-parse failures from the Opsgenie API; propagate unknown exceptions.

    ``retry_after`` is the 429 response's Retry-After delay in seconds, or ``None`` when the
    header is absent (Opsgenie documents only X-RateLimit-State) or not a number of seconds.
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
