"""Unit tests for a refused token request at first use of the Google client.

The tenant is built from a throwaway service-account key
(tests.factories.google_service_account), so the credentials are real and no token
has been fetched. The token request is stubbed at google.oauth2._client's
_token_endpoint_request, which raises RefreshError exactly as the library does for an
error response from the token endpoint. Logs are captured with structlog's
capture_logs. The assertions show the cause is logged as the OAuth error code, the
raised error carries a fixed message, and neither holds the library's text or the key.
"""

from pathlib import Path
from typing import Any

import httplib2
import pytest
from google.oauth2 import _client as oauth2_client
from structlog.testing import capture_logs

from contracts.operations.status import OperationStatus
from integrations.google_workspace import client as google_client
from integrations.google_workspace.settings import get_google_workspace_settings
from tests.factories.google_service_account import private_key_body, service_account_key
from tests.unit.integrations.google_workspace.conftest import install_google_files

pytestmark = pytest.mark.unit

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


@pytest.fixture(autouse=True)
def _tenant(google_slice_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_google_files(tmp_path)
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "C0tenant0001")
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY", service_account_key())
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL", "bot@example.com")


def _token_endpoint_answers(monkeypatch: pytest.MonkeyPatch, response: dict[str, Any] | str) -> None:
    def _refuse(*args: Any, **kwargs: Any) -> Any:
        oauth2_client._handle_error_response(response, False)

    monkeypatch.setattr(oauth2_client, "_token_endpoint_request", _refuse)
    monkeypatch.setattr(httplib2.Http, "request", lambda *a, **k: pytest.fail("an API request was sent without a token"))


def _first_call(monkeypatch: pytest.MonkeyPatch) -> google_client.GoogleCredentialsRefused:
    service = google_client.get_drive_service(DRIVE_SCOPES)
    with pytest.raises(google_client.GoogleCredentialsRefused) as raised:
        service.files().list().execute()
    return raised.value


@pytest.mark.parametrize(
    ("response", "cause"),
    [
        ({"error": "invalid_grant", "error_description": "Invalid JWT Signature."}, "invalid_grant"),
        ({"error": "unauthorized_client", "error_description": "Client is unauthorized"}, "unauthorized_client"),
        ("<html>gateway said no</html>", "unknown"),
    ],
)
def test_a_refused_token_logs_the_cause_and_raises_a_fixed_message(
    monkeypatch: pytest.MonkeyPatch, response: dict[str, Any] | str, cause: str
) -> None:
    _token_endpoint_answers(monkeypatch, response)

    with capture_logs() as entries:
        refused = _first_call(monkeypatch)

    assert refused.cause == cause
    assert str(refused) == google_client.GoogleCredentialsRefused.message
    assert {"event": "google_token_refused", "cause": cause, "log_level": "error"} in entries
    rendered = repr(entries) + str(refused)
    for text in ("Invalid JWT Signature", "Client is unauthorized", "gateway said no", private_key_body()):
        assert text not in rendered


def test_the_refusal_is_classified_as_unauthorized_with_its_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapters classify it like a 401, so callers show their stable unauthorized message."""
    _token_endpoint_answers(monkeypatch, {"error": "invalid_grant"})

    status, code, retry_after = google_client.classify_google_error(_first_call(monkeypatch))

    assert (status, code, retry_after) == (OperationStatus.UNAUTHORIZED, "invalid_grant", None)


def test_building_a_service_fetches_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the first API call asks for a token; building the slice and the service does not."""
    monkeypatch.setattr(oauth2_client, "_token_endpoint_request", lambda *a, **k: pytest.fail("token fetched"))

    google_client.get_drive_service(DRIVE_SCOPES)

    assert get_google_workspace_settings().tenant is not None


def test_every_service_derives_from_the_credentials_built_at_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    """The key is parsed once by the slice, never again per call."""
    monkeypatch.setattr(google_client, "build", lambda *a, **k: k["http"])
    tenant = get_google_workspace_settings().tenant
    assert tenant is not None

    first = google_client.get_drive_service(DRIVE_SCOPES)
    second = google_client.get_sheets_service(["https://www.googleapis.com/auth/spreadsheets"])

    for http in (first, second):
        assert http.credentials.signer is tenant.credentials.signer
