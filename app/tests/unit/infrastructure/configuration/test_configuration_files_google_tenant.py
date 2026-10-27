"""Tests for the Google Workspace tenant in the checked-in configuration files.

The tenant entry is environment only: its customer id and delegated user are
non-public values and its key a secret (decisions/configuration.md), so no
checked-in file names it. Each environment's files are read with the real loader
and the Google slice is built on them with every tenant variable blanked; the
raw files are also searched for the tenant table, a key, an email and anything
shaped like a Drive id.
"""

import re
from collections.abc import Iterator

import pytest

from contracts.configuration import install_configuration_files
from integrations.google_workspace.settings import GoogleWorkspaceSettings
from server.configuration.loader import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit

# Drive file and folder ids are 19 to 44 URL-safe characters mixing digits or capitals in; the lower
# snake_case error codes of [slack] hold neither. The CamelCase boto3 error-code lists of [aws] do, so
# they are cut out before the search.
_AWS_CODE_LISTS = re.compile(r"^(?:not_found|unauthorized|transient)_codes = \[.*?^\]$", re.DOTALL | re.MULTILINE)
_DRIVE_ID_SHAPE = re.compile(r"[\"'](?=[A-Za-z0-9_-]*[A-Z0-9])[A-Za-z0-9_-]{19,}[\"']")


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the slice from the files only, never a developer's .env or Codespaces secrets."""
    monkeypatch.setitem(GoogleWorkspaceSettings.model_config, "env_file", None)
    for field in ("CUSTOMER_ID", "SERVICE_ACCOUNT_KEY", "DELEGATED_USER_EMAIL"):
        monkeypatch.setenv(f"GOOGLE_WORKSPACE__TENANT__{field}", "")
    yield


@pytest.mark.parametrize("environment", ["production", "local", "ci"])
def test_configuration_files_name_no_google_tenant(environment: str) -> None:
    """No environment's files configure a tenant: it comes only from GOOGLE_WORKSPACE__TENANT__<FIELD>."""
    install_configuration_files(load_configuration_files(environment))

    assert GoogleWorkspaceSettings().tenant is None


@pytest.mark.parametrize("name", ["base.toml", "local.toml", "ci.toml", "production.toml"])
def test_configuration_files_hold_no_google_tenant_value(name: str) -> None:
    """No checked-in file carries the tenant table, a customer id, the key, the delegated user, an email or a Drive id."""
    text = (CONFIG_DIR / name).read_text(encoding="utf-8")
    values = "\n".join(line for line in _AWS_CODE_LISTS.sub("", text).splitlines() if not line.lstrip().startswith("#"))

    for marker in ("google_workspace.tenant", "customer_id", "private_key", "service_account_key", "delegated_user_email", "@"):
        assert marker not in values
    assert _DRIVE_ID_SHAPE.search(values) is None
