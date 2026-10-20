"""Unit tests for the Google Workspace tenant id (GOOGLE_WORKSPACE_CUSTOMER_ID).

Settings are built from monkeypatched environment variables with the .env file
disabled; building them makes no network call. Google is in use when its
service-account key is set (the interim signal until the tenant entry exists),
and then the customer id must be the real one: never blank and never the
my_customer API alias. The id is opaque (Google documents no format).
"""

import pytest
from pydantic import ValidationError

from integrations.google_workspace.settings import GoogleWorkspaceSettings

pytestmark = pytest.mark.unit


@pytest.fixture
def google_in_use(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", '{"type": "service_account"}')
    monkeypatch.delenv("GOOGLE_WORKSPACE_CUSTOMER_ID", raising=False)


@pytest.fixture
def google_unused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", "")
    monkeypatch.delenv("GOOGLE_WORKSPACE_CUSTOMER_ID", raising=False)


@pytest.mark.usefixtures("google_in_use")
@pytest.mark.parametrize("value", [None, "my_customer", "", "  "])
def test_in_use_without_a_real_customer_id_fails_naming_the_key(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """The default, the alias and blank values are not a tenant id, so boot fails naming the key."""
    if value is not None:
        monkeypatch.setenv("GOOGLE_WORKSPACE_CUSTOMER_ID", value)

    with pytest.raises(ValidationError, match="GOOGLE_WORKSPACE_CUSTOMER_ID"):
        GoogleWorkspaceSettings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.usefixtures("google_in_use")
@pytest.mark.parametrize("customer_id", ["C03abc123", "C0123456789abcdefghij"])
def test_in_use_accepts_any_other_non_blank_customer_id(monkeypatch: pytest.MonkeyPatch, customer_id: str) -> None:
    """No format is assumed for the customer id."""
    monkeypatch.setenv("GOOGLE_WORKSPACE_CUSTOMER_ID", customer_id)

    assert customer_id == GoogleWorkspaceSettings(_env_file=None).GOOGLE_WORKSPACE_CUSTOMER_ID  # type: ignore[call-arg]


@pytest.mark.usefixtures("google_unused")
def test_unused_keeps_the_default_without_a_check() -> None:
    """Without the key Google is not configured, so nothing is required (CI, local runs)."""
    assert GoogleWorkspaceSettings(_env_file=None).GOOGLE_WORKSPACE_CUSTOMER_ID == "my_customer"  # type: ignore[call-arg]


@pytest.mark.usefixtures("google_unused")
def test_unused_accepts_an_explicit_real_customer_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting the id ahead of the key is harmless."""
    monkeypatch.setenv("GOOGLE_WORKSPACE_CUSTOMER_ID", "C03abc123")

    assert GoogleWorkspaceSettings(_env_file=None).GOOGLE_WORKSPACE_CUSTOMER_ID == "C03abc123"  # type: ignore[call-arg]
