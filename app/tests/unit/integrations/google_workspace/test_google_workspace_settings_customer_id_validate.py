"""Unit tests for the Google Workspace tenant entry (customer id and service-account key).

Settings are built from monkeypatched environment variables with the .env file
disabled; building them makes no network call. The entry is present when the
service-account key or the customer id is set, and a present entry needs both:
the key, and the real customer id, never blank and never the my_customer API
alias. Each failure names the missing variable. The id is opaque (Google
documents no format). With neither set, Google is not configured.
"""

import pytest
from pydantic import ValidationError

from integrations.google_workspace.settings import GoogleWorkspaceSettings, GoogleWorkspaceTenant

pytestmark = pytest.mark.unit

KEY = '{"type": "service_account"}'


@pytest.fixture
def key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", KEY)
    monkeypatch.delenv("GOOGLE_WORKSPACE_CUSTOMER_ID", raising=False)


@pytest.fixture
def key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", "")
    monkeypatch.delenv("GOOGLE_WORKSPACE_CUSTOMER_ID", raising=False)


@pytest.mark.usefixtures("key_set")
@pytest.mark.parametrize("value", [None, "my_customer", "", "  "])
def test_key_without_a_real_customer_id_fails_naming_the_key(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """An unset id, the alias and blank values are not a tenant id, so boot fails naming the id's key."""
    if value is not None:
        monkeypatch.setenv("GOOGLE_WORKSPACE_CUSTOMER_ID", value)

    with pytest.raises(ValidationError, match="GOOGLE_WORKSPACE_CUSTOMER_ID"):
        GoogleWorkspaceSettings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.usefixtures("key_unset")
@pytest.mark.parametrize("value", ["C03abc123", "my_customer"])
def test_customer_id_without_the_key_fails_naming_the_key_file(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """A present entry requires its secret, so an id set without the key fails boot naming the key's variable."""
    monkeypatch.setenv("GOOGLE_WORKSPACE_CUSTOMER_ID", value)

    with pytest.raises(ValidationError, match="GCP_SRE_SERVICE_ACCOUNT_KEY_FILE"):
        GoogleWorkspaceSettings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.usefixtures("key_set")
@pytest.mark.parametrize("customer_id", ["C03abc123", "C0123456789abcdefghij"])
def test_key_and_id_build_the_entry_with_any_non_blank_id(monkeypatch: pytest.MonkeyPatch, customer_id: str) -> None:
    """No format is assumed for the customer id; the entry carries it stripped, with the key."""
    monkeypatch.setenv("GOOGLE_WORKSPACE_CUSTOMER_ID", f" {customer_id} ")

    tenant = GoogleWorkspaceSettings(_env_file=None).tenant  # type: ignore[call-arg]

    assert tenant == GoogleWorkspaceTenant(customer_id=customer_id, service_account_key=KEY)


@pytest.mark.usefixtures("key_unset")
@pytest.mark.parametrize("value", [None, ""])
def test_neither_set_means_no_entry_and_no_default(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """Without the key or the id Google is not configured (CI, local runs): no entry, and no alias default."""
    if value is not None:
        monkeypatch.setenv("GOOGLE_WORKSPACE_CUSTOMER_ID", value)

    settings = GoogleWorkspaceSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.tenant is None
    assert settings.google_workspace_customer_id is None


def test_entry_repr_hides_the_service_account_key() -> None:
    """The key is a secret, so the entry's repr never shows it."""
    tenant = GoogleWorkspaceTenant(customer_id="C03abc123", service_account_key=KEY)

    assert "service_account" not in repr(tenant)
