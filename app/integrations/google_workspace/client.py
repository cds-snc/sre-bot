"""Google Workspace vendor client.

Provides authenticated Google API service construction (Admin SDK Directory,
Calendar, Meet, Docs) and shared error classification per
decisions/outbound-clients.md — clients raise typed SDK exceptions; adapters
classify them. Each factory returns a stub-typed Resource built with the
narrow OAuth scopes its caller needs.
"""

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

import google_auth_httplib2
import httplib2
import structlog
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest

from infrastructure.configuration.integrations.google import get_google_workspace_settings
from infrastructure.operations.status import OperationStatus

if TYPE_CHECKING:
    from googleapiclient._apis.admin.directory_v1 import (  # pyright: ignore[reportMissingModuleSource]
        DirectoryResource as AdminDirectoryResource,
    )
    from googleapiclient._apis.calendar.v3 import CalendarResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.docs.v1 import DocsResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.drive.v3 import DriveResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.meet.v2 import MeetResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.sheets.v4 import SheetsResource  # pyright: ignore[reportMissingModuleSource]

logger = structlog.get_logger()

_NOT_FOUND_STATUSES = {404}
_UNAUTHORIZED_STATUSES = {401, 403}
_TRANSIENT_STATUSES = {429, 500, 502, 503, 504}


class _DefaultingRetryHttpRequest(HttpRequest):
    """Apply the configured retry count when a request does not specify one."""

    def __init__(self, *args: Any, default_num_retries: int, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._default_num_retries = default_num_retries

    def execute(self, http: Any = None, num_retries: int | None = None, **kwargs: Any) -> Any:
        resolved_num_retries = self._default_num_retries if num_retries is None else num_retries
        return super().execute(http=http, num_retries=resolved_num_retries, **kwargs)


def _build_request_builder(num_retries: int) -> Callable[..., HttpRequest]:
    """Build a request constructor carrying the service's retry default."""

    def request_builder(*args: Any, **kwargs: Any) -> HttpRequest:
        return _DefaultingRetryHttpRequest(*args, default_num_retries=num_retries, **kwargs)

    return request_builder


def _build_authorized_http(credentials: Any, timeout_seconds: float) -> google_auth_httplib2.AuthorizedHttp:
    """Build a new authorized http with an explicit per-attempt timeout.

    Mirrors googleapiclient.http.build_http, which otherwise falls back to the
    library's 60-second default: 308 is removed from the automatic redirect codes
    because Drive resumable uploads use it as a status rather than a redirect.
    """
    http = httplib2.Http(timeout=timeout_seconds)
    http.redirect_codes = http.redirect_codes - {308}
    return google_auth_httplib2.AuthorizedHttp(credentials, http=http)


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


def get_docs_service(
    scopes: list[str],
    delegated_user_email: str | None = None,
) -> DocsResource:
    """Build an authenticated Docs API service resource."""
    return cast("DocsResource", _build_service("docs", "v1", scopes, delegated_user_email))


def get_drive_service(
    scopes: list[str],
    delegated_user_email: str | None = None,
) -> DriveResource:
    """Build an authenticated Google Drive API service resource."""
    return cast("DriveResource", _build_service("drive", "v3", scopes, delegated_user_email))


def get_sheets_service(
    scopes: list[str],
    delegated_user_email: str | None = None,
) -> SheetsResource:
    """Build an authenticated Sheets API service resource."""
    return cast("SheetsResource", _build_service("sheets", "v4", scopes, delegated_user_email))


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

    # Timeout and retry policy are both fixed here, once per service: the http
    # carries the per-attempt timeout, and resource construction propagates the
    # request builder to nested resources so every call inherits one SDK-native
    # retry policy without call-site drift. httplib2.Http is not thread-safe, so
    # each built service owns a new http; never cache or share one.
    return build(
        api_name,
        api_version,
        http=_build_authorized_http(creds, settings.GOOGLE_API_TIMEOUT_SECONDS),
        cache_discovery=False,
        static_discovery=True,
        requestBuilder=_build_request_builder(settings.GOOGLE_API_NUM_RETRIES),
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
