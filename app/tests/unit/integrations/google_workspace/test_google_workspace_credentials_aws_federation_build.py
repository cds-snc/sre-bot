"""Unit tests for the ECS adapter's federation chain: STS exchange, then impersonation.

The AWS side is a fake supplier returning fixed task-role credentials; every HTTP exchange
goes through a recording fake transport answering like Google STS and IAM Credentials, so
no network is used. The tenant-level test builds the slice from the environment with
outbound sockets blocked, which shows boot builds the chain without a network call. The
assertions show:
- the STS request carries the configured audience and, as the subject token, an AWS-signed
  GetCallerIdentity request to the supplier's regional STS host (compared as a parsed host,
  never as a substring);
- the federated token then impersonates the service account for the caller's scopes;
- no key is read.
"""

import json
import socket
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from google.auth import aws, impersonated_credentials

from integrations.google_workspace.client import aws_federation_source, credential_source
from integrations.google_workspace.settings import GoogleWorkspaceSettings
from tests.unit.integrations.google_workspace.conftest import install_google_files

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("no_regional_access_boundary_lookup")]

# google-auth's regional access boundary lookup is switched off (conftest); should it run,
# the fakes answer "no boundary" and leave it out of the recorded calls.
_NO_BOUNDARY: dict[str, object] = {"encodedLocations": "0x0", "locations": []}

AUDIENCE = "//iam.googleapis.com/projects/123456789012/locations/global/workloadIdentityPools/sre-bot/providers/aws-ecs"
SERVICE_ACCOUNT = "sre-bot@cdssnc.iam.gserviceaccount.com"
DRIVE = ["https://www.googleapis.com/auth/drive"]


class _Supplier(aws.AwsSecurityCredentialsSupplier):
    def get_aws_security_credentials(self, context: Any, request: Any) -> aws.AwsSecurityCredentials:
        return aws.AwsSecurityCredentials("AKIATASKROLE", "task-role-secret", "task-role-session-token")

    def get_aws_region(self, context: Any, request: Any) -> str:
        return "ca-central-1"


class _Transport:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, method: str = "GET", body: Any = None, headers: Any = None, **kwargs: Any) -> Any:
        if url.endswith("/allowedLocations"):
            return _response(_NO_BOUNDARY)
        text = body.decode() if isinstance(body, bytes) else body
        self.calls.append({"url": url, "body": text, "headers": dict(headers or {})})
        if url == "https://sts.googleapis.com/v1/token":
            return _response(
                {
                    "access_token": "federated-token",
                    "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                }
            )
        if url.endswith(":generateAccessToken"):
            return _response({"accessToken": "service-account-token", "expireTime": "2099-01-01T00:00:00Z"})
        pytest.fail(f"unexpected request to {url}")


def _response(body: dict[str, Any]) -> Any:
    return SimpleNamespace(status=200, data=json.dumps(body).encode("utf-8"), headers={})


def test_the_task_role_is_exchanged_at_sts_then_impersonates_the_service_account() -> None:
    """The proof of identity is the AWS-signed request; no key is involved anywhere in the chain."""
    transport = _Transport()
    credentials = aws_federation_source(AUDIENCE, SERVICE_ACCOUNT, _Supplier()).for_call(DRIVE, None)

    credentials.refresh(transport)

    exchange, impersonation = transport.calls
    form = parse_qs(exchange["body"])
    assert form["audience"] == [AUDIENCE]
    assert form["subject_token_type"] == ["urn:ietf:params:aws:token-type:aws4_request"]
    subject_token = json.loads(unquote(form["subject_token"][0]))
    signed_request = urlsplit(subject_token["url"])
    assert (signed_request.scheme, signed_request.hostname) == ("https", "sts.ca-central-1.amazonaws.com")
    assert parse_qs(signed_request.query)["Action"] == ["GetCallerIdentity"]
    assert impersonation["url"].endswith(f"/serviceAccounts/{SERVICE_ACCOUNT}:generateAccessToken")
    assert impersonation["headers"]["authorization"] == "Bearer federated-token"
    assert json.loads(impersonation["body"])["scope"] == DRIVE
    assert credentials.token == "service-account-token"


def test_the_tenant_builds_the_federated_chain_at_boot_without_network(
    google_slice_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the audience and the email set, every factory's credentials come from STS and impersonation."""
    install_google_files(tmp_path)
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "C0tenant0001")
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL", SERVICE_ACCOUNT)
    monkeypatch.setenv("AWS_REGION", "ca-central-1")
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: pytest.fail("network used at boot"))

    tenant = GoogleWorkspaceSettings().tenant
    assert tenant is not None
    credentials = credential_source(tenant).for_call(DRIVE, None)

    assert tenant.authentication == "aws_federation"
    assert isinstance(credentials, impersonated_credentials.Credentials)
    assert credentials.service_account_email == SERVICE_ACCOUNT
    assert isinstance(credentials._source_credentials, aws.Credentials)
    assert credentials._source_credentials.info["audience"] == AUDIENCE
