"""Unit tests for the Google Workspace tenant entry's boot rules.

Each test installs its own files and sets only the variables it needs
(``google_slice_env``, ``install_google_files``); building the slice makes no
network call. The tenant entry is read from GOOGLE_WORKSPACE__TENANT__<FIELD>: a
customer id needs the service-account key; the key or the delegated user set
without a customer id fails; the customer id is the real one, never blank or the
my_customer alias (the id is opaque: Google documents no format). Failures are read
from the ConfigurationError message, which must name the variable, and the
rendered traceback is searched for the key, the customer id and the delegated
user's values, which must never appear.
"""

import traceback
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError
from integrations.google_workspace.settings import GoogleWorkspaceSettings
from tests.unit.integrations.google_workspace.conftest import install_google_files

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("google_slice_env")]

KEY = '{"type": "service_account", "private_key": "secret-key-0001"}'
CUSTOMER = "C0tenant0001"
DELEGATED_USER = "delegated-user-0001@example.com"
CUSTOMER_NAME = "GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID"
KEY_NAME = "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY"
DELEGATED_NAME = "GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL"


def _build_error() -> str:
    with pytest.raises(ConfigurationError) as caught:
        GoogleWorkspaceSettings()
    rendered = "".join(traceback.format_exception(caught.value))
    for value in (KEY, "secret-key-0001", DELEGATED_USER, CUSTOMER):
        assert value not in rendered
    return str(caught.value)


def test_customer_id_without_the_key_fails_naming_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A tenant is unusable without its credential, so boot fails naming the key's variable."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(DELEGATED_NAME, DELEGATED_USER)

    assert f"{KEY_NAME} is required when {CUSTOMER_NAME} is set" in _build_error()


@pytest.mark.parametrize("name", [KEY_NAME, DELEGATED_NAME])
def test_a_tenant_value_without_the_customer_id_fails_naming_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """A key or delegated user with no customer id is a half configuration, so boot fails naming the variable."""
    install_google_files(tmp_path)
    monkeypatch.setenv(name, DELEGATED_USER if name == DELEGATED_NAME else KEY)

    assert f"{name} is set but {CUSTOMER_NAME} is not" in _build_error()


def test_empty_tenant_variables_count_as_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank variables, as the test run sets them, are absent: no tenant and no failure."""
    install_google_files(tmp_path)
    for name in (CUSTOMER_NAME, KEY_NAME, DELEGATED_NAME):
        monkeypatch.setenv(name, "")

    assert GoogleWorkspaceSettings().tenant is None


def test_an_empty_delegated_user_with_a_tenant_is_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank delegated user beside a configured tenant is no delegated user, not an empty subject."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(KEY_NAME, KEY)
    monkeypatch.setenv(DELEGATED_NAME, "")

    tenant = GoogleWorkspaceSettings().tenant

    assert tenant is not None
    assert tenant.delegated_user_email is None


def test_an_empty_key_with_a_customer_id_fails_naming_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank key is no key: the tenant fails rather than building a half tenant."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(KEY_NAME, "")

    assert KEY_NAME in _build_error()


@pytest.mark.parametrize("customer_id", ["  ", "my_customer"])
def test_a_blank_or_alias_customer_id_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, customer_id: str) -> None:
    """Whitespace and the my_customer alias are not a tenant id, so boot fails naming the variable."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, customer_id)
    monkeypatch.setenv(KEY_NAME, KEY)

    assert CUSTOMER_NAME in _build_error()


def test_the_customer_id_is_stripped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Surrounding whitespace is not part of the id the directory calls send."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, f" {CUSTOMER} ")
    monkeypatch.setenv(KEY_NAME, KEY)

    tenant = GoogleWorkspaceSettings().tenant

    assert tenant is not None
    assert tenant.customer_id == CUSTOMER


@pytest.mark.parametrize(
    "files",
    [
        "[google_workspace]\nunknown = 1\n",
        "[google_workspace]\n[google_workspace.tenant]\nunknown = 1\n",
    ],
)
def test_an_unknown_key_fails(tmp_path: Path, files: str) -> None:
    """A misspelt key in the table or the tenant entry fails boot instead of being ignored."""
    install_google_files(tmp_path, base=files)

    assert "unknown" in _build_error()


def test_the_repr_hides_every_tenant_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Logging the slice or its tenant never prints the credential or the non-public values."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(KEY_NAME, KEY)
    monkeypatch.setenv(DELEGATED_NAME, DELEGATED_USER)

    settings = GoogleWorkspaceSettings()

    for text in (repr(settings), repr(settings.tenant), str(settings)):
        for value in (KEY, CUSTOMER, DELEGATED_USER):
            assert value not in text
