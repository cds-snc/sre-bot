"""Unit tests for the AWS tenant entry's boot rules and the [aws] key check.

Each test installs its own files (``install_aws_files``), sets only the AWS__TENANT__<FIELD>
variables it needs and builds the slice; no network call is made. The entry exists when the
instance id is set and then needs the instance ARN, both checked against the formats AWS
documents (IdentityStoreId and the sso-admin InstanceArn); an ARN or role without an instance
id is a half configuration; the three role ARNs are individually optional and an empty value
counts as unset. A malformed entry or an unknown key fails with a ConfigurationError that
names the variable or key.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError
from integrations.aws.settings import AWSSettings
from tests.unit.integrations.aws.conftest import INSTANCE_ARN, INSTANCE_ID, install_aws_files

pytestmark = pytest.mark.unit

ID_NAME = "AWS__TENANT__INSTANCE_ID"
ARN_NAME = "AWS__TENANT__INSTANCE_ARN"


@pytest.fixture(autouse=True)
def _files(tmp_path: Path) -> None:
    install_aws_files(tmp_path)


def _fails_naming(key: str) -> str:
    with pytest.raises(ConfigurationError) as caught:
        AWSSettings()
    assert key in str(caught.value)
    return str(caught.value)


def test_instance_id_without_the_instance_arn_fails_naming_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """An instance id without its ARN is half an instance, so boot fails naming the ARN's variable."""
    monkeypatch.setenv(ID_NAME, INSTANCE_ID)

    _fails_naming(ARN_NAME)


@pytest.mark.parametrize("name", [ARN_NAME, "AWS__TENANT__ORG_ROLE_ARN"])
def test_a_tenant_value_without_the_instance_id_fails_naming_it(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """An ARN or role without an instance id is a half configuration, so boot fails naming the variable."""
    monkeypatch.setenv(name, INSTANCE_ARN)

    assert f"{name} is set but {ID_NAME} is not" in _fails_naming(name)


@pytest.mark.parametrize("value", ["1234567890", "d-12345678AB", "d-123456789"])
def test_instance_id_off_the_documented_format_fails_naming_the_variable(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """The identity store id is d- and ten hex digits (or a UUID); anything else fails naming its variable."""
    monkeypatch.setenv(ID_NAME, value)
    monkeypatch.setenv(ARN_NAME, INSTANCE_ARN)

    message = _fails_naming(ID_NAME)

    assert value not in message


def test_instance_id_accepts_the_uuid_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The identity store id also takes the UUID form AWS documents."""
    uuid = "12345678-90ab-cdef-1234-567890abcdef"
    monkeypatch.setenv(ID_NAME, uuid)
    monkeypatch.setenv(ARN_NAME, INSTANCE_ARN)

    assert AWSSettings().identity_store_id == uuid


@pytest.mark.parametrize("value", ["", "ssoins-1234567890abcdef", "arn:aws:sso:::instance/ssoins-short"])
def test_instance_arn_off_the_documented_format_fails_naming_the_variable(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """The instance ARN follows the sso-admin InstanceArn pattern; anything else fails naming its variable."""
    monkeypatch.setenv(ID_NAME, INSTANCE_ID)
    monkeypatch.setenv(ARN_NAME, value)

    _fails_naming(ARN_NAME)


def test_empty_values_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank tenant variables, as the test run sets them, leave the tenant absent."""
    for field in ("INSTANCE_ID", "INSTANCE_ARN", "AUDIT_ROLE_ARN", "ORG_ROLE_ARN", "LOGGING_ROLE_ARN"):
        monkeypatch.setenv(f"AWS__TENANT__{field}", "")

    assert AWSSettings().tenant is None


def test_empty_role_arns_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tenant with empty role values keeps the bot's own credentials for every service."""
    monkeypatch.setenv(ID_NAME, INSTANCE_ID)
    monkeypatch.setenv(ARN_NAME, INSTANCE_ARN)
    for field in ("AUDIT_ROLE_ARN", "ORG_ROLE_ARN", "LOGGING_ROLE_ARN"):
        monkeypatch.setenv(f"AWS__TENANT__{field}", "")

    settings = AWSSettings()

    assert settings.service_role_map == {}
    assert settings.identity_store_id == INSTANCE_ID


def test_unknown_key_in_the_aws_table_fails_naming_the_key(tmp_path: Path) -> None:
    """A misspelt tuning key stops boot instead of silently running on the default."""
    install_aws_files(tmp_path, "[aws]\nretry_max_attemps = 3\n")

    _fails_naming("retry_max_attemps")


def test_unknown_key_in_the_tenant_fails_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A misspelt tenant variable stops boot naming the key."""
    monkeypatch.setenv(ID_NAME, INSTANCE_ID)
    monkeypatch.setenv(ARN_NAME, INSTANCE_ARN)
    monkeypatch.setenv("AWS__TENANT__ORG_ROLE", "x")

    _fails_naming("org_role")
