"""Unit tests for the boot-time shape check of the tenant's service-account key.

A present tenant's key must parse as strict JSON with type service_account, and
google-auth must build credentials from it locally. Each test installs its own files
(``install_google_files``) and sets the tenant variables; keys come from
tests.factories.google_service_account, a throwaway RSA key. socket.socket is replaced
with a class that raises, so any network call during the check fails the test. A
failure names GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY, and the rendered traceback
must never hold the key material.
"""

import json
import socket
import traceback
from pathlib import Path

import pytest
from google.oauth2 import service_account

from contracts.configuration import ConfigurationError
from integrations.google_workspace.settings import GoogleWorkspaceSettings
from tests.factories.google_service_account import CLIENT_EMAIL, private_key_body, service_account_info, service_account_key
from tests.unit.integrations.google_workspace.conftest import install_google_files

pytestmark = pytest.mark.unit

KEY_NAME = "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY"


class _NoNetwork(socket.socket):
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("the key check opened a socket")


@pytest.fixture(autouse=True)
def _tenant(google_slice_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_google_files(tmp_path)
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "C0tenant0001")
    monkeypatch.setattr(socket, "socket", _NoNetwork)


def _build_error(monkeypatch: pytest.MonkeyPatch, key: str) -> str:
    monkeypatch.setenv(KEY_NAME, key)
    with pytest.raises(ConfigurationError) as caught:
        GoogleWorkspaceSettings()
    rendered = "".join(traceback.format_exception(caught.value))
    assert private_key_body() not in rendered
    return str(caught.value)


def test_a_valid_key_builds_the_credentials_once_with_no_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """The credentials are built at boot and the same object is handed to every caller."""
    monkeypatch.setenv(KEY_NAME, service_account_key())

    tenant = GoogleWorkspaceSettings().tenant

    assert tenant is not None
    assert isinstance(tenant.credentials, service_account.Credentials)
    assert tenant.credentials.service_account_email == CLIENT_EMAIL
    assert tenant.credentials is tenant.credentials


def test_a_private_key_with_literal_newlines_fails_naming_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A secret pasted with real newlines inside private_key is not strict JSON (seen in a Codespaces secret)."""
    pem = service_account_info()["private_key"]
    broken = service_account_key().replace(json.dumps(pem)[1:-1], pem)

    message = _build_error(monkeypatch, broken)

    assert KEY_NAME in message
    assert "is not valid JSON" in message


def test_a_key_that_is_not_an_object_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "is not a JSON object" in _build_error(monkeypatch, "[1, 2]")


def test_a_key_of_another_type_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """An OAuth client secret or an authorized-user file is not a service-account key."""
    message = _build_error(monkeypatch, service_account_key(type="authorized_user"))

    assert KEY_NAME in message
    assert "type must be service_account" in message


@pytest.mark.parametrize("field", ["client_email", "private_key", "token_uri"])
def test_a_missing_field_fails_naming_it(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    message = _build_error(monkeypatch, service_account_key(**{field: None}))

    assert KEY_NAME in message
    assert f"is missing {field}" in message


def test_an_unreadable_private_key_fails_without_quoting_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A truncated PEM cannot be loaded into a signer; the message names the problem, not the key."""
    pem = service_account_info()["private_key"]
    truncated = pem[: len(pem) // 2]

    message = _build_error(monkeypatch, service_account_key(private_key=truncated))

    assert KEY_NAME in message
    assert "private_key that cannot be loaded" in message
    assert truncated.splitlines()[3] not in message
