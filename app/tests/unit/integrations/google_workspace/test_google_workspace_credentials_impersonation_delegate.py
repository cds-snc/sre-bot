"""Unit tests for the keyless credentials every non-key source hands the client.

The federated and application-default sources both impersonate the bot's service account
from a source credential. The source here is a fake google-auth credential that already
holds a token, and every HTTP exchange goes through a recording fake transport that answers
like IAM Credentials and the OAuth token endpoint, so no network is used. The assertions
show:
- with a subject, the token is minted keylessly through signJwt and the JWT grant;
- without one, it comes from generateAccessToken;
- each request carries exactly the caller's scopes;
- the same subject and scopes reuse one credentials object;
- IAM's refusal reaches callers as GoogleCredentialsRefused with the refusal's status as its
  cause.
"""

import json
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs

import google_auth_httplib2
import pytest
from google.auth import credentials as google_credentials
from google.auth import impersonated_credentials
from structlog.testing import capture_logs

from integrations.google_workspace import client as google_client
from integrations.google_workspace.client import ImpersonatingCredentialSource

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("no_regional_access_boundary_lookup")]

# google-auth's regional access boundary lookup is switched off (conftest); should it run,
# the fakes answer "no boundary" and leave it out of the recorded calls.
_NO_BOUNDARY: dict[str, object] = {"encodedLocations": "0x0", "locations": []}

SERVICE_ACCOUNT = "sre-bot@cdssnc.iam.gserviceaccount.com"
SUBJECT = "sre-bot@example.com"
DRIVE = ["https://www.googleapis.com/auth/drive"]
CALENDAR = ["https://www.googleapis.com/auth/calendar.events"]


class _SourceCredentials(google_credentials.Credentials):
    """A source credential that already holds a token, as a refreshed STS or user credential does."""

    def __init__(self) -> None:
        super().__init__()
        self.token = "source-token"

    def refresh(self, request: Any) -> None:
        pytest.fail("the source credential was refreshed although it held a valid token")


class _Transport:
    """Answers IAM Credentials and the OAuth token endpoint; records every request."""

    def __init__(self, iam_status: int = 200, iam_body: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.iam_status = iam_status
        self.iam_body = iam_body

    def __call__(self, url: str, method: str = "GET", body: Any = None, headers: Any = None, **kwargs: Any) -> Any:
        if url.endswith("/allowedLocations"):
            return _response(200, _NO_BOUNDARY)
        self.calls.append({"url": url, "method": method, "body": body, "headers": dict(headers or {})})
        if ":signJwt" in url or ":generateAccessToken" in url:
            if self.iam_status != 200:
                return _response(self.iam_status, self.iam_body or {})
            if ":signJwt" in url:
                return _response(200, {"keyId": "system-managed", "signedJwt": "header.claims.signature"})
            return _response(200, {"accessToken": "service-account-token", "expireTime": "2099-01-01T00:00:00Z"})
        if url == "https://oauth2.googleapis.com/token":
            return _response(200, {"access_token": "delegated-token", "expires_in": 3600})
        pytest.fail(f"unexpected request to {url}")


def _response(status: int, body: dict[str, Any]) -> Any:
    return SimpleNamespace(status=status, data=json.dumps(body).encode("utf-8"), headers={})


def _source() -> ImpersonatingCredentialSource:
    return ImpersonatingCredentialSource(SERVICE_ACCOUNT, _SourceCredentials)


def test_a_subject_delegates_through_sign_jwt_and_the_jwt_grant() -> None:
    """Domain-wide delegation needs no key: IAM signs the assertion with Google's own key."""
    transport = _Transport()
    credentials = _source().for_call(CALENDAR, SUBJECT)

    credentials.refresh(transport)

    sign, grant = transport.calls
    assert sign["url"].endswith(f"/serviceAccounts/{SERVICE_ACCOUNT}:signJwt")
    assert sign["headers"]["authorization"] == "Bearer source-token"
    claims = json.loads(json.loads(sign["body"])["payload"])
    assert (claims["iss"], claims["sub"], claims["scope"]) == (SERVICE_ACCOUNT, SUBJECT, CALENDAR[0])
    assert parse_qs(grant["body"].decode() if isinstance(grant["body"], bytes) else grant["body"])["assertion"] == [
        "header.claims.signature"
    ]
    assert credentials.token == "delegated-token"


def test_no_subject_impersonates_the_service_account_itself() -> None:
    """The bot acting as itself takes a service-account token for exactly the caller's scopes."""
    transport = _Transport()
    credentials = _source().for_call(DRIVE, None)

    credentials.refresh(transport)

    (call,) = transport.calls
    assert call["url"].endswith(f"/serviceAccounts/{SERVICE_ACCOUNT}:generateAccessToken")
    assert json.loads(call["body"])["scope"] == DRIVE
    assert credentials.token == "service-account-token"


def test_one_credentials_object_per_subject_and_scope_set() -> None:
    """A token is minted once per principal and scopes, then refreshes itself; other scopes get their own."""
    source = _source()

    first = source.for_call(DRIVE, SUBJECT)

    assert source.for_call(list(DRIVE), SUBJECT) is first
    assert source.for_call(DRIVE, None) is not first
    assert source.for_call(CALENDAR, SUBJECT) is not first
    assert isinstance(first, impersonated_credentials.Credentials)


def test_the_source_credential_is_resolved_once_on_first_use() -> None:
    """Building the source does nothing; the first call resolves the source credential, later calls reuse it."""
    resolved: list[_SourceCredentials] = []

    def _resolve() -> _SourceCredentials:
        resolved.append(_SourceCredentials())
        return resolved[-1]

    source = ImpersonatingCredentialSource(SERVICE_ACCOUNT, _resolve)
    assert resolved == []

    source.for_call(DRIVE, None)
    source.for_call(CALENDAR, SUBJECT)

    assert len(resolved) == 1


def test_an_iam_refusal_reaches_callers_as_refused_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing Token Creator grant is classified like a refused key: unauthorized, with IAM's status as the cause."""
    transport = _Transport(
        iam_status=403,
        iam_body={
            "error": {
                "code": 403,
                "message": "Permission 'iam.serviceAccounts.getAccessToken' denied",
                "status": "PERMISSION_DENIED",
            }
        },
    )
    monkeypatch.setattr(google_auth_httplib2.Request, "__call__", lambda self, *a, **k: transport(*a, **k))
    http = google_client._build_authorized_http(_source().for_call(DRIVE, None), 5.0)

    with capture_logs() as entries, pytest.raises(google_client.GoogleCredentialsRefused) as raised:
        http.request("https://www.googleapis.com/drive/v3/files")

    assert raised.value.cause == "permission_denied"
    assert {"event": "google_token_refused", "cause": "permission_denied", "log_level": "error"} in entries
    assert "getAccessToken" not in repr(entries) + str(raised.value)
