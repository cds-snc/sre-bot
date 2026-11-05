"""Unit tests for the platform default: application default credentials impersonating the bot.

A developer's gcloud login, a GCP runtime, or a Workload Identity Federation credential
configuration file for another platform all arrive through google.auth.default, and the
gateway impersonates the service account from them (decisions/service-accounts.md rule 5).
google.auth.default is patched where the test is about when it runs. The credential-file
test runs the real resolution against an external_account file whose subject token is a
local file, with every HTTP exchange answered by one recording fake transport (google.auth's
requests transport is patched too, since google.auth.default resolves the file's project
once through STS and Cloud Resource Manager), which shows another platform needs no code
and no key. The assertions show resolution waits for the
first call, happens once across concurrent first calls, and a missing login reaches callers
as refused credentials.
"""

import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs

import google.auth
import google.auth.transport.requests
import pytest
from google.auth import credentials as google_credentials
from google.auth.exceptions import DefaultCredentialsError

from integrations.google_workspace import client as google_client
from integrations.google_workspace.client import application_default_source

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("no_regional_access_boundary_lookup")]

# google-auth's regional access boundary lookup is switched off (conftest); should it run,
# the fakes answer "no boundary" and leave it out of the recorded calls.
_NO_BOUNDARY: dict[str, object] = {"encodedLocations": "0x0", "locations": []}

SERVICE_ACCOUNT = "sre-bot-dev@cdssnc.iam.gserviceaccount.com"
DRIVE = ["https://www.googleapis.com/auth/drive"]
AUDIENCE = "//iam.googleapis.com/projects/123456789012/locations/global/workloadIdentityPools/other-cloud/providers/oidc-issuer"


class _UserCredentials(google_credentials.Credentials):
    def __init__(self) -> None:
        super().__init__()
        self.token = "developer-token"

    def refresh(self, request: Any) -> None:
        pytest.fail("refreshed although a token was held")


def test_nothing_is_resolved_until_the_first_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Boot makes no metadata probe and reads no login: only the first Google call resolves them."""
    calls: list[Any] = []
    monkeypatch.setattr(google.auth, "default", lambda **kwargs: calls.append(kwargs) or (_UserCredentials(), None))

    source = application_default_source(SERVICE_ACCOUNT)
    assert calls == []

    credentials = source.for_call(DRIVE, None)

    assert calls == [{"scopes": ["https://www.googleapis.com/auth/cloud-platform"]}]
    assert credentials.service_account_email == SERVICE_ACCOUNT


def test_concurrent_first_calls_resolve_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two requests arriving together share one resolution."""
    calls: list[int] = []
    started = threading.Barrier(4)

    def _default(**kwargs: Any) -> Any:
        calls.append(1)
        return _UserCredentials(), None

    monkeypatch.setattr(google.auth, "default", _default)
    source = application_default_source(SERVICE_ACCOUNT)

    def _call(scopes: list[str]) -> None:
        started.wait()
        source.for_call(scopes, None)

    threads = [threading.Thread(target=_call, args=([f"https://www.googleapis.com/auth/scope{n}"],)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls == [1]


def test_no_login_reaches_callers_as_refused_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer who has not run gcloud auth application-default login gets the stable unauthorized error."""

    def _missing(**kwargs: Any) -> Any:
        raise DefaultCredentialsError("Your default credentials were not found at /home/someone/.config/gcloud")

    monkeypatch.setattr(google.auth, "default", _missing)
    settings = SimpleNamespace(tenant=SimpleNamespace(delegated_user_email=None), api_num_retries=0, api_timeout_seconds=5.0)
    monkeypatch.setattr(google_client, "get_google_workspace_settings", lambda: settings)
    monkeypatch.setattr(google_client, "credential_source", lambda tenant: application_default_source(SERVICE_ACCOUNT))

    with pytest.raises(google_client.GoogleCredentialsRefused) as raised:
        google_client.get_drive_service(DRIVE)

    assert raised.value.cause == "application_default_credentials_unavailable"
    assert "/home/someone" not in str(raised.value)


def test_a_credential_configuration_file_federates_another_platform_without_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An OIDC token file (Kubernetes, OpenShift, Azure through a helper) is exchanged at STS, then impersonates the bot."""
    token_file = tmp_path / "token"
    token_file.write_text("platform-oidc-token", encoding="utf-8")
    configuration = tmp_path / "credential-configuration.json"
    configuration.write_text(
        json.dumps(
            {
                "type": "external_account",
                "audience": AUDIENCE,
                "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
                "token_url": "https://sts.googleapis.com/v1/token",
                "credential_source": {"file": str(token_file)},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(configuration))
    calls: list[dict[str, Any]] = []

    def _transport(url: str, method: str = "GET", body: Any = None, headers: Any = None, **kwargs: Any) -> Any:
        if url.endswith("/allowedLocations"):
            return SimpleNamespace(status=200, data=json.dumps(_NO_BOUNDARY).encode("utf-8"), headers={})
        text = body.decode() if isinstance(body, bytes) else body
        calls.append({"url": url, "body": text, "headers": dict(headers or {})})
        if url == "https://sts.googleapis.com/v1/token":
            payload: dict[str, Any] = {
                "access_token": "federated-token",
                "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        elif url.endswith(":generateAccessToken"):
            payload = {"accessToken": "service-account-token", "expireTime": "2099-01-01T00:00:00Z"}
        elif url.startswith("https://cloudresourcemanager.googleapis.com/"):
            payload = {"projectNumber": "123456789012", "projectId": "other-cloud-project"}
        else:
            pytest.fail(f"unexpected request to {url}")
        return SimpleNamespace(status=200, data=json.dumps(payload).encode("utf-8"), headers={})

    monkeypatch.setattr(google.auth.transport.requests.Request, "__call__", lambda self, *a, **k: _transport(*a, **k))

    credentials = application_default_source(SERVICE_ACCOUNT).for_call(DRIVE, None)
    credentials.refresh(_transport)

    exchange = next(call for call in calls if call["url"] == "https://sts.googleapis.com/v1/token")
    impersonation = next(call for call in calls if call["url"].endswith(":generateAccessToken"))
    assert {call["url"].split("/")[2] for call in calls} <= {
        "sts.googleapis.com",
        "cloudresourcemanager.googleapis.com",
        "iamcredentials.googleapis.com",
    }
    assert parse_qs(exchange["body"])["subject_token"] == ["platform-oidc-token"]
    assert parse_qs(exchange["body"])["audience"] == [AUDIENCE]
    assert impersonation["url"].endswith(f"/serviceAccounts/{SERVICE_ACCOUNT}:generateAccessToken")
    assert impersonation["headers"]["authorization"] == "Bearer federated-token"
    assert credentials.token == "service-account-token"
