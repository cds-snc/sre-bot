"""Unit tests for loading the AWS vendor slice from the [aws] table.

Each test installs a base and a local file from tmp_path (``install_aws_files``) with
every AWS variable removed and the .env file disabled (the autouse isolation fixture),
so it observes only the values it writes and sets. The client tuning comes from [aws];
the managed organisation from the optional tenant entry, read only from AWS__TENANT__<FIELD>
in the environment (no file names it); the region and the
dynamodb-local endpoint belong to the SDK and are not fields. The fifteen retired
AWS_* names are ignored in the environment and in a .env file.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationSlice
from integrations.aws.settings import AWSSettings, AwsTenant, get_aws_settings
from tests.factories.aws import set_aws_tenant
from tests.unit.integrations.aws.conftest import INSTANCE_ARN, INSTANCE_ID, RETIRED_NAMES, install_aws_files

pytestmark = pytest.mark.unit

ORG = "arn:aws:iam::123456789012:role/org-role"
AUDIT = "arn:aws:iam::123456789012:role/audit-role"
LOGGING = "arn:aws:iam::123456789012:role/logging-role"


def test_aws_settings_is_a_slice_on_the_aws_table() -> None:
    """The slice reads [aws] with the AWS__ prefix and rejects unknown keys."""
    config = AWSSettings.model_config

    assert issubclass(AWSSettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("aws",)
    assert config.get("env_prefix") == "AWS__"
    assert config.get("extra") == "forbid"


@pytest.mark.parametrize("field", list(AWSSettings.model_fields))
def test_aws_settings_fields_have_no_alias(field: str) -> None:
    """Every field is read only under its AWS__<FIELD> name or file key: no alias widens it."""
    info = AWSSettings.model_fields[field]

    assert (info.alias, info.validation_alias) == (None, None)


def test_aws_settings_declares_no_sdk_or_access_field(tmp_path: Path) -> None:
    """The region, the endpoint and the permission sets are not fields of the AWS slice."""
    install_aws_files(tmp_path)

    assert not {"aws_region", "dynamodb_endpoint_url", "system_admin_permissions", "view_only_permissions"} & set(
        AWSSettings.model_fields
    )
    assert not hasattr(AWSSettings(), "aws_region")


def test_aws_settings_reads_the_tuning_and_the_overrides(tmp_path: Path) -> None:
    """The base file's tuning applies; the environment file overrides it key by key."""
    base = (
        "[aws]\nretry_max_attempts = 3\nretry_mode = 'standard'\nconnect_timeout_seconds = 10\n"
        "read_timeout_seconds = 10\ntransient_retry_after_seconds = 60\n"
        "not_found_codes = ['A']\nunauthorized_codes = ['B']\ntransient_codes = ['C']\n"
    )
    install_aws_files(tmp_path, base, "[aws]\nretry_mode = 'adaptive'\nread_timeout_seconds = 7\n")

    settings = AWSSettings()

    assert (settings.retry_max_attempts, settings.retry_mode, settings.connect_timeout_seconds) == (3, "adaptive", 10)
    assert (settings.read_timeout_seconds, settings.transient_retry_after_seconds) == (7, 60)
    assert (settings.not_found_codes, settings.unauthorized_codes, settings.transient_codes) == (["A"], ["B"], ["C"])


def test_aws_settings_tenant_fills_the_role_map(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each service resolves to the role of the account that holds it; the instance pair is exposed."""
    install_aws_files(tmp_path)
    set_aws_tenant(
        monkeypatch,
        instance_id=INSTANCE_ID,
        instance_arn=INSTANCE_ARN,
        audit_role_arn=AUDIT,
        org_role_arn=ORG,
        logging_role_arn=LOGGING,
    )

    settings = AWSSettings()

    assert settings.service_role_map == {
        "organizations": ORG,
        "identitystore": ORG,
        "sso-admin": ORG,
        "ce": ORG,
        "audit": AUDIT,
        "config": AUDIT,
        "logging": LOGGING,
        "guardduty": LOGGING,
        "securityhub": LOGGING,
    }
    assert (settings.identity_store_id, settings.sso_instance_arn) == (INSTANCE_ID, INSTANCE_ARN)
    assert settings.tenant == AwsTenant(
        instance_id=INSTANCE_ID, instance_arn=INSTANCE_ARN, audit_role_arn=AUDIT, org_role_arn=ORG, logging_role_arn=LOGGING
    )


def test_aws_settings_org_role_only_maps_the_org_services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With only the org role named, as in production, only the org-role services get an entry."""
    install_aws_files(tmp_path)
    set_aws_tenant(monkeypatch, instance_id=INSTANCE_ID, instance_arn=INSTANCE_ARN, org_role_arn=ORG)

    role_map = AWSSettings().service_role_map

    assert role_map == {"organizations": ORG, "identitystore": ORG, "sso-admin": ORG, "ce": ORG}
    assert role_map.get("audit") is None
    assert role_map.get("logging") is None


def test_aws_settings_without_a_tenant_has_no_roles_and_empty_instance_values(tmp_path: Path) -> None:
    """An absent tenant keeps today's behaviour: the bot's own credentials and empty instance values."""
    install_aws_files(tmp_path)

    settings = AWSSettings()

    assert settings.tenant is None
    assert settings.service_role_map == {}
    assert (settings.identity_store_id, settings.sso_instance_arn) == ("", "")


def test_aws_settings_tenant_reads_from_a_dotenv_file(tmp_path: Path) -> None:
    """A developer's .env file supplies the tenant entry under the same names."""
    install_aws_files(tmp_path)
    dotenv = tmp_path / ".env"
    dotenv.write_text(f"AWS__TENANT__INSTANCE_ID={INSTANCE_ID}\nAWS__TENANT__INSTANCE_ARN={INSTANCE_ARN}\n", encoding="utf-8")

    settings = AWSSettings(_env_file=dotenv)  # type: ignore[call-arg]

    assert settings.identity_store_id == INSTANCE_ID


@pytest.mark.parametrize("name", RETIRED_NAMES)
def test_aws_settings_ignores_a_retired_name_in_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """A retired AWS_* name changes nothing and does not trip the unknown-key check."""
    install_aws_files(tmp_path)
    monkeypatch.setenv(name, "5" if "ATTEMPTS" in name or "SECONDS" in name else "ignored")

    settings = AWSSettings()

    assert settings.tenant is None
    assert settings.retry_max_attempts == 3
    assert settings.retry_mode == "standard"


def test_aws_settings_ignores_the_retired_names_in_a_dotenv_file(tmp_path: Path) -> None:
    """A developer's .env still holding the retired lines boots with the files' values."""
    install_aws_files(tmp_path)
    dotenv = tmp_path / ".env"
    dotenv.write_text("".join(f"{name}=ignored\n" for name in RETIRED_NAMES), encoding="utf-8")

    settings = AWSSettings(_env_file=dotenv)  # type: ignore[call-arg]

    assert settings.tenant is None
    assert settings.retry_mode == "standard"


def test_get_aws_settings_is_cached_until_cleared(tmp_path: Path) -> None:
    """The provider returns one instance per process until its cache is cleared."""
    install_aws_files(tmp_path)

    first = get_aws_settings()

    assert get_aws_settings() is first
    get_aws_settings.cache_clear()
    assert get_aws_settings() is not first
