"""Google Workspace vendor client.

Provides authenticated Google API service construction (Admin SDK Directory,
Calendar, Meet, Docs) and shared error classification per
decisions/outbound-clients.md — clients raise typed SDK exceptions; adapters
classify them. Each factory returns a stub-typed Resource built with the
narrow OAuth scopes its caller needs.

Credential construction (decisions/service-accounts.md rule 5): the settings slice chooses
the source at boot; ``credential_source`` builds it once per tenant, with no network call:
- AWS federation is the ECS adapter. google-auth's built-in AWS source reads only
  environment variables or EC2 metadata, and Fargate has neither, so
  ``BotocoreCredentialsSupplier`` hands google-auth the botocore session's task-role
  credentials; Google STS exchanges them and the service account is impersonated.
- Application default credentials are the platform default: a developer's gcloud login, a
  GCP runtime, or a Workload Identity Federation credential configuration file for another
  platform (``GOOGLE_APPLICATION_CREDENTIALS``, no key, no code), then impersonation.
- The key is tolerated until TASK-182.
On both keyless sources domain-wide delegation goes through IAM signJwt. Each (subject,
scopes) pair gets one credentials object that refreshes itself.
The first token is fetched when the first API call runs. So a refused federation, a
missing Token Creator grant, a revoked key, a missing developer login or a missing
domain-wide delegation surfaces there, as GoogleCredentialsRefused: the refusal's code
is logged as the cause and the message is fixed, never the library's text.
"""

import json
import re
import threading
from collections.abc import Callable, Sequence
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol, cast

import botocore.session
import google.auth
import google_auth_httplib2
import httplib2
import structlog
from google.auth import aws, impersonated_credentials
from google.auth import credentials as google_credentials
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest

from contracts.operations.status import OperationStatus
from integrations.google_workspace.settings import GoogleWorkspaceTenant, get_google_workspace_settings

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
# An OAuth error code (RFC 6749 section 5.2) is lower snake case; anything else is not logged.
_OAUTH_ERROR_CODE = re.compile(r"^[a-z_]{1,64}$")
# google-auth's STS errors start "Error code <code>: ..."; only the code is kept.
_STS_ERROR_CODE = re.compile(r"^Error code ([a-z_]{1,64})\b")


# The source credential only calls IAM Credentials, which takes the cloud-platform scope.
_CLOUD_PLATFORM = "https://www.googleapis.com/auth/cloud-platform"
_AWS4_REQUEST_SUBJECT = "urn:ietf:params:aws:token-type:aws4_request"
# Google's maximum for a service-account access token without an organisation exception.
_TOKEN_LIFETIME_SECONDS = 3600
# Callers use a fixed set of (subject, scopes) pairs; the bound only guards against a defect.
_MAX_CACHED_CALLS = 64


class GoogleCredentialSource(Protocol):
    """Hands the client the credentials for one call: the caller's scopes, optionally as a delegated user."""

    def for_call(self, scopes: Sequence[str], subject: str | None) -> google_credentials.Credentials:
        """Return credentials limited to ``scopes``, acting as ``subject`` through domain-wide delegation when set."""
        ...


class KeyCredentialSource:
    """The stored key, tolerated until TASK-182: copies of the boot-time credentials per call."""

    def __init__(self, credentials: service_account.Credentials) -> None:
        self._credentials = credentials

    def for_call(self, scopes: Sequence[str], subject: str | None) -> google_credentials.Credentials:
        credentials = self._credentials
        if subject:
            credentials = credentials.with_subject(subject)
        if scopes:
            credentials = credentials.with_scopes(list(scopes))
        return credentials


class ImpersonatingCredentialSource:
    """Impersonates the bot's service account from a source credential resolved on first use.

    With a subject, IAM signs the delegation assertion (signJwt) and the token endpoint
    grants a delegated token; without one, IAM issues the service account's own token.
    """

    def __init__(self, service_account_email: str, resolve_source: Callable[[], google_credentials.Credentials]) -> None:
        self._service_account_email = service_account_email
        self._resolve_source = resolve_source
        self._source: google_credentials.Credentials | None = None
        self._calls: dict[tuple[str | None, frozenset[str]], impersonated_credentials.Credentials] = {}
        self._lock = threading.Lock()

    def for_call(self, scopes: Sequence[str], subject: str | None) -> google_credentials.Credentials:
        key = (subject or None, frozenset(scopes))
        with self._lock:
            cached = self._calls.get(key)
            if cached is None:
                if self._source is None:
                    self._source = self._resolve_source()
                if len(self._calls) >= _MAX_CACHED_CALLS:
                    self._calls.clear()
                cached = impersonated_credentials.Credentials(
                    source_credentials=self._source,
                    target_principal=self._service_account_email,
                    target_scopes=sorted(scopes),
                    subject=subject or None,
                    lifetime=_TOKEN_LIFETIME_SECONDS,
                )
                self._calls[key] = cached
        return cached


class BotocoreCredentialsSupplier(aws.AwsSecurityCredentialsSupplier):
    """The ECS task role's credentials for Google STS, read from the botocore session on every call.

    botocore's credentials object refreshes itself before the task role's credentials expire,
    so each call returns the current frozen set. A failure is reported as a fixed code: the
    library's text can name the credentials endpoint or the role.
    """

    def __init__(self, session: Any, region: str) -> None:
        self._session = session
        self._region = region
        self._credentials: Any = None

    def get_aws_security_credentials(self, context: Any, request: Any) -> aws.AwsSecurityCredentials:
        try:
            if self._credentials is None:
                self._credentials = self._session.get_credentials()
            if self._credentials is None:
                raise LookupError
            frozen = self._credentials.get_frozen_credentials()
        except Exception:
            raise RefreshError("aws_credentials_unavailable") from None
        return aws.AwsSecurityCredentials(frozen.access_key, frozen.secret_key, frozen.token)

    def get_aws_region(self, context: Any, request: Any) -> str:
        return self._region


def aws_federation_source(
    audience: str, service_account_email: str, supplier: aws.AwsSecurityCredentialsSupplier
) -> ImpersonatingCredentialSource:
    """The ECS adapter: task-role credentials exchanged at Google STS, then impersonation of the service account."""

    def _resolve() -> google_credentials.Credentials:
        return aws.Credentials(
            audience=audience,
            subject_token_type=_AWS4_REQUEST_SUBJECT,
            aws_security_credentials_supplier=supplier,
            scopes=[_CLOUD_PLATFORM],
        )

    return ImpersonatingCredentialSource(service_account_email, _resolve)


def application_default_source(service_account_email: str) -> ImpersonatingCredentialSource:
    """The platform default: whatever google.auth.default finds, impersonating the service account."""

    def _resolve() -> google_credentials.Credentials:
        credentials, _ = google.auth.default(scopes=[_CLOUD_PLATFORM])
        return cast(google_credentials.Credentials, credentials)

    return ImpersonatingCredentialSource(service_account_email, _resolve)


@lru_cache(maxsize=4)
def credential_source(tenant: GoogleWorkspaceTenant) -> GoogleCredentialSource:
    """The tenant's credential source, built once on the first Google call; never a network call."""
    if tenant.authentication == "aws_federation":
        return aws_federation_source(
            str(tenant.federation_audience),
            str(tenant.service_account_email),
            BotocoreCredentialsSupplier(botocore.session.get_session(), tenant.aws_region),
        )
    if tenant.authentication == "key":
        return KeyCredentialSource(tenant.credentials)
    return application_default_source(str(tenant.service_account_email))


class GoogleCredentialsRefused(Exception):
    """Google refused the service account's token request; ``cause`` is the OAuth error code."""

    message = "Google Workspace refused the bot's credentials. An administrator must check the bot's Google identity and its delegation."

    def __init__(self, cause: str) -> None:
        super().__init__(self.message)
        self.cause = cause


def _token_error_code(error: RefreshError) -> str:
    """The refusal's code, or unknown.

    The token endpoint's OAuth code (invalid_grant, unauthorized_client), IAM Credentials'
    status lower-cased (permission_denied), STS's code (invalid_grant), or the fixed code of
    a source that failed before any request (aws_credentials_unavailable).
    """
    details = error.args[1] if len(error.args) > 1 else None
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except ValueError:
            details = None
    code: object = None
    if isinstance(details, dict):
        code = details.get("error")
        if isinstance(code, dict):
            status = code.get("status")
            code = status.lower() if isinstance(status, str) else None
    first = error.args[0] if error.args else None
    if not isinstance(code, str) and isinstance(first, str):
        sts = _STS_ERROR_CODE.match(first)
        code = sts.group(1) if sts else first.split(":", 1)[0].strip()
    return code if isinstance(code, str) and _OAUTH_ERROR_CODE.match(code) else "unknown"


class _TokenCheckedHttp(google_auth_httplib2.AuthorizedHttp):
    """AuthorizedHttp that reports a refused token request as GoogleCredentialsRefused."""

    def request(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return super().request(*args, **kwargs)
        except RefreshError as error:
            cause = _token_error_code(error)
            logger.error("google_token_refused", cause=cause)
            raise GoogleCredentialsRefused(cause) from None


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


def _build_authorized_http(credentials: Any, timeout_seconds: float) -> _TokenCheckedHttp:
    """Build a new authorized http with an explicit per-attempt timeout.

    Mirrors googleapiclient.http.build_http, which otherwise falls back to the
    library's 60-second default: 308 is removed from the automatic redirect codes
    because Drive resumable uploads use it as a status rather than a redirect.
    """
    http = httplib2.Http(timeout=timeout_seconds)
    http.redirect_codes = http.redirect_codes - {308}
    return _TokenCheckedHttp(credentials, http=http)


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
    tenant = settings.tenant
    if tenant is None:
        logger.error("google_workspace_not_configured", api_name=api_name, api_version=api_version)
        raise ValueError(
            "Google Workspace is not configured: set GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID and a credential "
            "(integrations/google_workspace/README.md, service identity)"
        )

    # The source was chosen at boot; a keyless source resolves its source credential here, on
    # the first call, and reuses one credentials object per subject and scopes.
    delegation_email = delegated_user_email or tenant.delegated_user_email
    try:
        creds = credential_source(tenant).for_call(scopes, delegation_email or None)
    except DefaultCredentialsError:
        # No developer login or credential file: the library's text names local paths.
        cause = "application_default_credentials_unavailable"
        logger.error("google_token_refused", cause=cause)
        raise GoogleCredentialsRefused(cause) from None

    # Timeout and retry policy are both fixed here, once per service: the http
    # carries the per-attempt timeout, and resource construction propagates the
    # request builder to nested resources so every call inherits one SDK-native
    # retry policy without call-site drift. httplib2.Http is not thread-safe, so
    # each built service owns a new http; never cache or share one.
    return build(
        api_name,
        api_version,
        http=_build_authorized_http(creds, settings.api_timeout_seconds),
        cache_discovery=False,
        static_discovery=True,
        requestBuilder=_build_request_builder(settings.api_num_retries),
    )


def classify_google_error(exc: Exception) -> tuple[OperationStatus, str | None, int | None]:
    """Classify expected googleapiclient HttpError statuses and refused credentials; propagate unknown exceptions."""
    if isinstance(exc, GoogleCredentialsRefused):
        return OperationStatus.UNAUTHORIZED, exc.cause, None
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
