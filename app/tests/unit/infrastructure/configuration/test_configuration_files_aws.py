"""Tests for the AWS tenant and permission sets in the checked-in configuration files.

The tenant entry is environment only: the Identity Center identity store id and instance
ARN are internal tenant identifiers (the id is also the default access-portal subdomain)
and the permission-set ARNs embed the instance id, so they are non-public values
(decisions/configuration.md) and no checked-in file names them. Each environment's files
are read with the real loader and the slices are built on them with every tenant variable
blanked; the raw files are also searched for the tenant table, an instance id or ARN, a
permission-set ARN and anything credential-shaped.
"""

import tomllib
from collections.abc import Iterator

import pytest

from contracts.configuration import install_configuration_files
from integrations.aws.settings import AWSSettings
from packages.access.common.settings import AccessPermissionSetsSettings
from server.configuration.loader import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit

_TENANT_VARIABLES = (
    "AWS__TENANT__INSTANCE_ID",
    "AWS__TENANT__INSTANCE_ARN",
    "AWS__TENANT__AUDIT_ROLE_ARN",
    "AWS__TENANT__ORG_ROLE_ARN",
    "AWS__TENANT__LOGGING_ROLE_ARN",
    "ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS",
    "ACCESS_PERMISSION_SETS__VIEW_ONLY_PERMISSIONS",
)
_MARKERS = (
    "aws.tenant",
    "instance_id",
    "instance_arn",
    "role_arn",
    "arn:aws",
    "ssoins-",
    "d-",
    "permissionset",
    "AKIA",
    "ASIA",
    "secret_access_key",
    "session_token",
)


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the slices from the files only, never a developer's .env or Codespaces secrets."""
    monkeypatch.setitem(AWSSettings.model_config, "env_file", None)
    monkeypatch.setitem(AccessPermissionSetsSettings.model_config, "env_file", None)
    for name in _TENANT_VARIABLES:
        monkeypatch.setenv(name, "")
    yield


@pytest.mark.parametrize("environment", ["production", "local", "ci"])
def test_configuration_files_name_no_aws_tenant(environment: str) -> None:
    """No environment's files configure a tenant: it comes only from AWS__TENANT__<FIELD>."""
    install_configuration_files(load_configuration_files(environment))

    settings = AWSSettings()

    assert settings.tenant is None
    assert settings.service_role_map == {}
    assert (settings.identity_store_id, settings.sso_instance_arn) == ("", "")


@pytest.mark.parametrize("environment", ["production", "local", "ci"])
def test_configuration_files_name_no_permission_set(environment: str) -> None:
    """No environment's files name a permission-set ARN: both come only from the environment."""
    install_configuration_files(load_configuration_files(environment))

    settings = AccessPermissionSetsSettings()

    assert (settings.system_admin_permissions, settings.view_only_permissions) == ("", "")


def test_base_file_holds_the_tuning_and_the_empty_permission_set_keys() -> None:
    """The base file declares the tuning and the two empty permission-set keys, never a tenant."""
    base = tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))

    assert "tenant" not in base["aws"]
    assert base["access_permission_sets"] == {"system_admin_permissions": "", "view_only_permissions": ""}
    assert set(base["aws"]) == {
        "retry_max_attempts",
        "retry_mode",
        "connect_timeout_seconds",
        "read_timeout_seconds",
        "transient_retry_after_seconds",
        "not_found_codes",
        "unauthorized_codes",
        "transient_codes",
    }


@pytest.mark.parametrize("name", ["base.toml", "local.toml", "ci.toml", "production.toml"])
def test_configuration_files_hold_no_aws_tenant_value(name: str) -> None:
    """No checked-in file carries the tenant table, an instance id or ARN, a role or permission-set ARN or a credential."""
    text = (CONFIG_DIR / name).read_text(encoding="utf-8")
    values = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#")).lower()

    for marker in _MARKERS:
        assert marker.lower() not in values
