"""Google Workspace Admin SDK Directory vendor client.

Provides authenticated Directory API service construction and error
classification per decisions/outbound-clients.md — clients raise typed SDK
exceptions; adapters (infrastructure/directory/google.py) classify them.
"""

import json
from typing import TYPE_CHECKING, Any, cast

import structlog
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from infrastructure.configuration.integrations.google import get_google_workspace_settings
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

if TYPE_CHECKING:
    from googleapiclient._apis.admin.directory_v1 import (  # pyright: ignore[reportMissingModuleSource]
        DirectoryResource as AdminDirectoryResource,
    )
    from googleapiclient._apis.calendar.v3 import CalendarResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.meet.v2 import MeetResource  # pyright: ignore[reportMissingModuleSource]

logger = structlog.get_logger()

_NOT_FOUND_STATUSES = {404}
_UNAUTHORIZED_STATUSES = {401, 403}
_TRANSIENT_STATUSES = {429, 500, 502, 503, 504}


def get_admin_directory_service(
    scopes: list[str],
    delegated_user_email: str | None = None,
) -> AdminDirectoryResource:
    """Build an authenticated Admin SDK Directory API service resource.

    Builds a fresh, narrowly-scoped Resource per call (no shared long-lived
    client) so each operation delegates with only the OAuth scopes it needs.
    Raises on credential/build failure; callers classify errors raised from
    the returned Resource's calls with classify_google_error.
    """
    return cast("AdminDirectoryResource", _build_service("admin", "directory_v1", scopes, delegated_user_email))


def get_calendar_service(
    scopes: list[str],
    delegated_user_email: str | None = None,
) -> CalendarResource:
    """Build an authenticated Calendar API service resource."""
    return cast("CalendarResource", _build_service("calendar", "v3", scopes, delegated_user_email))


def get_meet_service(
    scopes: list[str],
    delegated_user_email: str | None = None,
) -> MeetResource:
    """Build an authenticated Meet API service resource."""
    return cast("MeetResource", _build_service("meet", "v2", scopes, delegated_user_email))


def _build_service(
    api_name: str,
    api_version: str,
    scopes: list[str],
    delegated_user_email: str | None,
) -> Any:
    settings = get_google_workspace_settings()

    try:
        creds_info = json.loads(settings.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE)
    except json.JSONDecodeError as exc:
        logger.error("invalid_credentials_json", error=str(exc))
        raise ValueError("Invalid credentials JSON") from exc

    creds = service_account.Credentials.from_service_account_info(creds_info)

    delegation_email = delegated_user_email or settings.SRE_BOT_EMAIL or None
    if delegation_email:
        creds = creds.with_subject(delegation_email)

    if scopes:
        creds = creds.with_scopes(scopes)

    # Use bundled discovery docs to avoid remote discovery fetches.
    return build(
        api_name,
        api_version,
        credentials=creds,
        cache_discovery=False,
        static_discovery=True,
    )


def classify_google_error(exc: Exception) -> tuple[OperationStatus, str | None, int | None]:
    """Classify expected googleapiclient HttpError statuses; propagate unknown exceptions."""
    if not isinstance(exc, HttpError):
        raise exc

    status = int(exc.resp.status)
    error_code = str(status)

    if status in _TRANSIENT_STATUSES:
        raw_retry_after = exc.resp.get("retry-after") if hasattr(exc.resp, "get") else None
        try:
            retry_after = int(raw_retry_after) if raw_retry_after is not None else None
        except TypeError, ValueError:
            retry_after = None
        return OperationStatus.TRANSIENT_ERROR, error_code, retry_after

    if status in _NOT_FOUND_STATUSES:
        return OperationStatus.NOT_FOUND, error_code, None

    if status in _UNAUTHORIZED_STATUSES:
        return OperationStatus.UNAUTHORIZED, error_code, None

    raise exc


def execute_google_api_request(request: Any) -> Any:
    """Execute a Google API request, logging classified failures and re-raising them.

    Temporary shared primitive: TASK-25.1.6 decides whether to inline this per
    call site or formalize it in decisions/outbound-clients.md.
    """
    try:
        return request.execute()
    except Exception as exc:
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning(
            "google_api_request_failed",
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        raise


def execute_batch_request(
    service: AdminDirectoryResource,
    requests: list[tuple[str, Any]],
) -> OperationResult[dict[str, Any]]:
    """Execute multiple Directory API calls in a single batch request.

    Per-item HttpErrors are captured per request_id (the Admin SDK batch
    protocol's own error-reporting shape) rather than raised individually.
    """
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}

    def callback(request_id: str, response: Any, exception: Exception | None) -> None:
        if exception is not None:
            errors[request_id] = str(exception)
        else:
            results[request_id] = response

    batch = service.new_batch_http_request(callback=callback)
    for request_id, api_request in requests:
        batch.add(api_request, request_id=request_id)
    batch.execute()

    if errors:
        return OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message="Batch request completed with errors",
            error_code="BATCH_ERRORS",
            data={"results": results, "errors": errors},
        )
    return OperationResult.success(data={"results": results, "errors": errors})
