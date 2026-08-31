"""Google Workspace Admin SDK Directory vendor client.

Provides authenticated Directory API service construction and error
classification per decisions/outbound-clients.md — clients raise typed SDK
exceptions; adapters (infrastructure/directory/google.py) classify them.
"""

import json
from typing import TYPE_CHECKING, Any

import structlog
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from infrastructure.configuration.integrations.google import get_google_workspace_settings
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

if TYPE_CHECKING:
    from googleapiclient._apis.admin.directory_v1 import DirectoryResource as AdminDirectoryResource

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
        "admin",
        "directory_v1",
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
