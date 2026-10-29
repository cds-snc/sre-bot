"""Unit tests for loading the Google Workspace vendor slice from the [google_workspace] table.

Each test installs a base and a local file from tmp_path (``install_google_files``)
with every Google variable removed and the .env file disabled (``google_slice_env``),
so it observes only the values it writes and sets. The non-secret values come from
the files; the tenant entry (customer id, service-account key, delegated user) only from
GOOGLE_WORKSPACE__TENANT__<FIELD> in the environment or a .env file the test passes.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, ConfigurationSlice
from integrations.google_workspace.settings import (
    GoogleWorkspaceSettings,
    get_google_workspace_settings,
)
from tests.factories.google_service_account import service_account_key
from tests.unit.integrations.google_workspace.conftest import install_google_files

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("google_slice_env")]

KEY = service_account_key()
DELEGATED_USER = "delegated-user-0001@example.com"
CUSTOMER = "C0tenant0001"


def test_google_settings_is_a_slice_on_the_google_workspace_table() -> None:
    """The slice reads [google_workspace] with the GOOGLE_WORKSPACE__ prefix and rejects unknown keys."""
    config = GoogleWorkspaceSettings.model_config

    assert issubclass(GoogleWorkspaceSettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("google_workspace",)
    assert config.get("env_prefix") == "GOOGLE_WORKSPACE__"
    assert config.get("extra") == "forbid"


@pytest.mark.parametrize("field", list(GoogleWorkspaceSettings.model_fields))
def test_google_settings_fields_have_no_alias(field: str) -> None:
    """Every field is read only under its GOOGLE_WORKSPACE__<FIELD> name or file key: no alias widens it."""
    info = GoogleWorkspaceSettings.model_fields[field]

    assert (info.alias, info.validation_alias) == (None, None)


def test_google_settings_reads_the_tuning_from_the_table(tmp_path: Path) -> None:
    """Retries and the per-attempt timeout come from [google_workspace]; without a tenant entry Google is unconfigured."""
    install_google_files(tmp_path, "[google_workspace]\napi_num_retries = 5\napi_timeout_seconds = 2.5\n")

    settings = GoogleWorkspaceSettings()

    assert (settings.api_num_retries, settings.api_timeout_seconds, settings.tenant) == (5, 2.5, None)


def test_google_settings_reads_the_tenant_from_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The customer id, the key and the delegated user come from their GOOGLE_WORKSPACE__TENANT__ variables."""
    install_google_files(tmp_path)
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", CUSTOMER)
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY", KEY)
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL", DELEGATED_USER)

    tenant = GoogleWorkspaceSettings().tenant

    assert tenant is not None
    assert (tenant.customer_id, tenant.service_account_key, tenant.delegated_user_email) == (CUSTOMER, KEY, DELEGATED_USER)


def test_google_settings_reads_the_tenant_secrets_from_a_dotenv_file(tmp_path: Path) -> None:
    """A developer's .env file supplies the tenant entry under the same names."""
    install_google_files(tmp_path)
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        f"GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID={CUSTOMER}\n"
        f"GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY='{KEY}'\n"
        f"GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL={DELEGATED_USER}\n",
        encoding="utf-8",
    )

    tenant = GoogleWorkspaceSettings(_env_file=dotenv).tenant  # type: ignore[call-arg]

    assert tenant is not None
    assert (tenant.customer_id, tenant.service_account_key, tenant.delegated_user_email) == (CUSTOMER, KEY, DELEGATED_USER)


def test_google_settings_delegated_user_is_optional(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A tenant with its key but no delegated user builds; callers then pass their own subject or none."""
    install_google_files(tmp_path)
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", CUSTOMER)
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY", KEY)

    tenant = GoogleWorkspaceSettings().tenant

    assert tenant is not None
    assert tenant.delegated_user_email is None


@pytest.mark.parametrize("timeout", ["0", "-1"])
def test_google_settings_non_positive_timeout_fails_naming_the_key(tmp_path: Path, timeout: str) -> None:
    """A timeout must be positive; the failure names the file and key."""
    install_google_files(tmp_path, f"[google_workspace]\napi_timeout_seconds = {timeout}\n")

    with pytest.raises(ConfigurationError, match=r"\[google_workspace\] api_timeout_seconds"):
        GoogleWorkspaceSettings()


def test_google_settings_provider_returns_one_cached_instance(tmp_path: Path) -> None:
    """Every caller shares one slice, so it is built and validated once."""
    install_google_files(tmp_path)

    assert get_google_workspace_settings() is get_google_workspace_settings()
