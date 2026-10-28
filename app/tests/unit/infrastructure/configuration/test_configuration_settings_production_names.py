"""Each settings slice reads its deployment environment names into the named field.

Every row sets one environment variable to a sentinel that differs from the
field default and builds the slice from the process environment only, so a
field rename that silently stops reading its name falls back to the default and
fails here instead of in production. The names are the deploy interface; the
security slice reads the configuration files and is pinned by its own
production-values test. The Slack slice
reads the [slack] table too: its secrets are pinned under their SLACK__<FIELD>
names (production sets SLACK__BOT_TOKEN, SLACK__USER_TOKEN and SLACK__APP_TOKEN
as task-definition secrets) beside a tenant entry, and the retired SLACK_<FIELD>
names are pinned as unread. The Google Workspace slice follows the same rule: its
key and delegated user are pinned under GOOGLE_WORKSPACE__TENANT__<FIELD> (production
sets both as task-definition secrets) beside a tenant entry, and the retired flat names
are pinned as unread; production still sets GOOGLE_RESOURCES. The AWS slice reads the [aws] table and its tenant entry from AWS__TENANT__<FIELD>
(production sets INSTANCE_ID, INSTANCE_ARN and ORG_ROLE_ARN as task-definition secrets),
and the access slice the [access_permission_sets] table with its two values from
ACCESS_PERMISSION_SETS__<FIELD>: non-public values, so no file names them; the fifteen
retired AWS_* names are pinned as unread; the region and the dynamodb-local endpoint are the SDK's
(AWS_DEFAULT_REGION, AWS_ENDPOINT_URL_DYNAMODB), declared by no field. The OpenAI slice
reads the [openai] table with its key under OPENAI__API_KEY (a task-definition secret) beside a
tenant entry; the six retired OPENAI_* names are pinned as unread. The Notify and
Opsgenie slices read their tables with their credentials under NOTIFY__SRE_USER_NAME,
NOTIFY__SRE_CLIENT_SECRET and OPSGENIE__INTEGRATIONS_KEY beside a tenant entry; Trello's
entry is its credentials, TRELLO__TENANT__APP_KEY and TRELLO__TENANT__TOKEN, with the board
under TRELLO__ATIP_BOARD; MaxMind's entry is its database file; their retired flat names
(and the unread TRELLO__APP_KEY and TRELLO__TOKEN) are pinned as unread. The Sentinel slice
still reads the SENTINEL_* names production sets, some of them written 'NAME =value' in the
.env file. The identity,
server, dev and Slack transport slices too: production sets ENVIRONMENT,
BACKEND_URL and SLACK__COMMAND_PREFIX (task definition), GIT_SHA (image),
NOTIFY_OPS_CHANNEL_ID, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SESSION_SECRET_KEY
and ACCESS_TOKEN_EXPIRE_MINUTES (the SSM-delivered sre-bot-config file), and
NOTIFY_ONCALL_GROUP_ID and SRE_TEST_CHANNEL_ID (sre-bot-config-infrastructure);
WEBHOOK_MAX_BODY_BYTES, ACCESS_TOKEN_MAX_AGE_MINUTES and SLACK_DEV_MSG_CHANNEL
stay part of the interface.
"""

from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings

from infrastructure.audit.settings import AuditSettings
from infrastructure.coordination.settings import ConditionalWriteSettings
from integrations.aws.settings import AWSSettings
from integrations.google_workspace.settings import GoogleResourcesConfig, GoogleWorkspaceSettings
from integrations.maxmind.settings import MaxMindSettings
from integrations.notify.settings import NotifySettings
from integrations.openai.settings import OpenAISettings
from integrations.opsgenie.settings import OpsGenieSettings
from integrations.sentinel.settings import SentinelSettings
from integrations.slack.settings import SlackSettings
from integrations.trello.settings import TrelloSettings
from packages.access.common.settings import AccessPermissionSetsSettings
from server.configuration import IdentitySettings

PRODUCTION_NAMES: list[tuple[type[BaseSettings], str, str, str, Any]] = [
    (AuditSettings, "AUDIT_TABLE_NAME", "audit_table_name", "sentinel_audit", "sentinel_audit"),
    (ConditionalWriteSettings, "IDEMPOTENCY_TTL_SECONDS", "idempotency_ttl_seconds", "1234", 1234),
    (
        ConditionalWriteSettings,
        "IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS",
        "idempotency_in_progress_ttl_seconds",
        "567",
        567,
    ),
    (
        GoogleResourcesConfig,
        "GOOGLE_RESOURCES",
        "resources",
        '{"inc":{"d":"sentinel-drive"}}',
        {"inc": {"d": "sentinel-drive"}},
    ),
    (SentinelSettings, "SENTINEL_CUSTOMER_ID", "sentinel_customer_id", "sentinel-customer", "sentinel-customer"),
    (SentinelSettings, "SENTINEL_LOG_TYPE", "sentinel_log_type", "SentinelLogs", "SentinelLogs"),
    (SentinelSettings, "SENTINEL_SHARED_KEY", "sentinel_shared_key", "sentinel-shared-key", "sentinel-shared-key"),
    (IdentitySettings, "ENVIRONMENT", "environment", "production", "production"),
    (IdentitySettings, "GIT_SHA", "git_sha", "sentinel-sha", "sentinel-sha"),
]


@pytest.mark.parametrize(
    ("settings_class", "env_name", "attribute", "raw", "expected"),
    PRODUCTION_NAMES,
    ids=[row[1] for row in PRODUCTION_NAMES],
)
def test_configuration_settings_production_name_reaches_field(
    monkeypatch: pytest.MonkeyPatch,
    settings_class: type[BaseSettings],
    env_name: str,
    attribute: str,
    raw: str,
    expected: Any,
) -> None:
    """The environment name sets the field; a fallback to the default would differ from the sentinel."""
    monkeypatch.setenv(env_name, raw)

    settings = settings_class(_env_file=None)  # type: ignore[call-arg]

    assert getattr(settings, attribute) == expected


def test_configuration_settings_lower_case_environment_name_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Names match case-insensitively, so the lower-case spelling of a name is read too."""
    monkeypatch.setenv("audit_table_name", "lower_sentinel")

    settings = AuditSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.audit_table_name == "lower_sentinel"


def test_configuration_settings_upper_case_keyword_accepted() -> None:
    """Constructor keywords in the environment spelling still set the lower-case field."""
    settings = ConditionalWriteSettings(_env_file=None, IDEMPOTENCY_TTL_SECONDS=42)  # type: ignore[call-arg]

    assert settings.idempotency_ttl_seconds == 42


SLACK_NAMES: list[tuple[str, str, str, Any]] = [
    ("SLACK__BOT_TOKEN", "bot_token", "xoxb-sentinel", "xoxb-sentinel"),
    ("SLACK__USER_TOKEN", "user_token", "xoxp-sentinel", "xoxp-sentinel"),
    ("SLACK__APP_TOKEN", "app_token", "xapp-sentinel", "xapp-sentinel"),
    ("SLACK__SIGNING_SECRET", "signing_secret", "sentinel-secret", "sentinel-secret"),
    ("SLACK__REQUEST_TIMEOUT_SECONDS", "request_timeout_seconds", "17", 17),
    ("SLACK__RETRY_MAX_ATTEMPTS", "retry_max_attempts", "5", 5),
    ("SLACK__TRANSIENT_RETRY_AFTER_SECONDS", "transient_retry_after_seconds", "41", 41),
    ("SLACK__UNAUTHORIZED_ERRORS", "unauthorized_errors", '["sentinel_unauth"]', ["sentinel_unauth"]),
    ("SLACK__NOT_FOUND_ERRORS", "not_found_errors", '["sentinel_missing"]', ["sentinel_missing"]),
    ("SLACK__TRANSIENT_ERRORS", "transient_errors", '["sentinel_transient"]', ["sentinel_transient"]),
]
"""A secret needs the tenant entry and the tenant entry needs the bot token, so every row sets both beside its name."""

SLACK_RETIRED_NAMES = [
    "SLACK_TEAM_ID",
    "SLACK_BOT_TOKEN",
    "SLACK_USER_TOKEN",
    "SLACK_APP_TOKEN",
    "SLACK_SIGNING_SECRET",
    "SLACK_REQUEST_TIMEOUT_SECONDS",
    "SLACK_RETRY_MAX_ATTEMPTS",
    "SLACK_TRANSIENT_RETRY_AFTER_SECONDS",
    "SLACK_UNAUTHORIZED_ERRORS",
    "SLACK_NOT_FOUND_ERRORS",
    "SLACK_TRANSIENT_ERRORS",
]


@pytest.mark.parametrize(("env_name", "attribute", "raw", "expected"), SLACK_NAMES, ids=[row[0] for row in SLACK_NAMES])
def test_configuration_settings_slack_name_reaches_field(
    monkeypatch: pytest.MonkeyPatch, env_name: str, attribute: str, raw: str, expected: Any
) -> None:
    """The SLACK__<FIELD> name sets the field; a fallback to the default would differ from the sentinel."""
    monkeypatch.setenv("SLACK__TENANT__TEAM_ID", "TSENTINEL1")
    monkeypatch.setenv("SLACK__BOT_TOKEN", "xoxb-companion")
    monkeypatch.setenv(env_name, raw)

    settings = SlackSettings(_env_file=None)  # type: ignore[call-arg]

    assert getattr(settings, attribute) == expected


def test_configuration_settings_slack_tenant_name_builds_the_tenant_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """SLACK__TENANT__TEAM_ID reaches the tenant entry, as [slack.tenant] team_id does in the files."""
    monkeypatch.setenv("SLACK__TENANT__TEAM_ID", "TSENTINEL1")
    monkeypatch.setenv("SLACK__BOT_TOKEN", "xoxb-companion")

    settings = SlackSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.tenant is not None
    assert settings.tenant.team_id == "TSENTINEL1"


@pytest.mark.parametrize("env_name", SLACK_RETIRED_NAMES)
def test_configuration_settings_slack_retired_name_is_unread(monkeypatch: pytest.MonkeyPatch, env_name: str) -> None:
    """The old SLACK_<FIELD> names and SLACK_TEAM_ID are read by no field: the slice builds exactly as without them."""
    baseline = SlackSettings(_env_file=None).model_dump()  # type: ignore[call-arg]
    monkeypatch.setenv(env_name, "7" if env_name.endswith(("SECONDS", "ATTEMPTS")) else "TSENTINEL1")

    settings = SlackSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.model_dump() == baseline


GOOGLE_NAMES: list[tuple[str, str, str, Any]] = [
    ("GOOGLE_WORKSPACE__API_NUM_RETRIES", "api_num_retries", "7", 7),
    ("GOOGLE_WORKSPACE__API_TIMEOUT_SECONDS", "api_timeout_seconds", "12.5", 12.5),
]

GOOGLE_RETIRED_NAMES = [
    "GOOGLE_DELEGATED_ADMIN_EMAIL",
    "SRE_BOT_EMAIL",
    "GOOGLE_WORKSPACE_CUSTOMER_ID",
    "GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
    "GOOGLE_API_NUM_RETRIES",
    "GOOGLE_API_TIMEOUT_SECONDS",
]


@pytest.mark.parametrize(("env_name", "attribute", "raw", "expected"), GOOGLE_NAMES, ids=[row[0] for row in GOOGLE_NAMES])
def test_configuration_settings_google_name_reaches_field(
    monkeypatch: pytest.MonkeyPatch, env_name: str, attribute: str, raw: str, expected: Any
) -> None:
    """The GOOGLE_WORKSPACE__<FIELD> name sets the field; a fallback to the default would differ from the sentinel."""
    monkeypatch.setenv(env_name, raw)

    settings = GoogleWorkspaceSettings(_env_file=None)  # type: ignore[call-arg]

    assert getattr(settings, attribute) == expected


def test_configuration_settings_google_tenant_names_build_the_tenant_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The key and the delegated user reach the tenant entry under their GOOGLE_WORKSPACE__TENANT__ names."""
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "C0sentinel")
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY", '{"type":"service_account"}')
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL", "bot@sentinel.example")

    tenant = GoogleWorkspaceSettings(_env_file=None).tenant  # type: ignore[call-arg]

    assert tenant is not None
    assert (tenant.customer_id, tenant.service_account_key, tenant.delegated_user_email) == (
        "C0sentinel",
        '{"type":"service_account"}',
        "bot@sentinel.example",
    )


@pytest.mark.parametrize("env_name", GOOGLE_RETIRED_NAMES)
def test_configuration_settings_google_retired_name_is_unread(monkeypatch: pytest.MonkeyPatch, env_name: str) -> None:
    """The old flat Google names are read by no field: the slice builds exactly as without them."""
    baseline = GoogleWorkspaceSettings(_env_file=None).model_dump()  # type: ignore[call-arg]
    monkeypatch.setenv(env_name, "7")

    settings = GoogleWorkspaceSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.model_dump() == baseline


def test_configuration_settings_slack_and_google_lower_case_names_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lower-case spelling of a Slack name and of a Google name is read too."""
    monkeypatch.setenv("slack__tenant__team_id", "TSENTINEL1")
    monkeypatch.setenv("slack__bot_token", "xoxb-lower")
    monkeypatch.setenv("google_workspace__api_num_retries", "9")

    slack = SlackSettings(_env_file=None)  # type: ignore[call-arg]
    google = GoogleWorkspaceSettings(_env_file=None)  # type: ignore[call-arg]

    assert slack.bot_token == "xoxb-lower"
    assert google.api_num_retries == 9


OPENAI_RETIRED_NAMES = [
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_MAX_OUTPUT_TOKENS",
    "OPENAI_TEMPERATURE",
    "OPENAI_TIMEOUT_SECONDS",
    "OPENAI_BASE_URL",
]

OPENAI_NAMES: list[tuple[str, str, Any]] = [
    ("OPENAI__MAX_OUTPUT_TOKENS", "max_output_tokens", 1234),
    ("OPENAI__TEMPERATURE", "temperature", 0.25),
    ("OPENAI__TIMEOUT_SECONDS", "timeout_seconds", 42.5),
]


def test_configuration_settings_openai_key_and_tenant_names_configure_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPENAI__API_KEY reaches the secret field beside a tenant entry; compared through its secret value."""
    monkeypatch.setenv("OPENAI__API_KEY", "sk-sentinel")
    monkeypatch.setenv("OPENAI__TENANT__BASE_URL", "https://ai.sentinel.example")
    monkeypatch.setenv("OPENAI__TENANT__MODEL", "sentinel-model")

    settings = OpenAISettings(_env_file=None)  # type: ignore[call-arg]

    assert isinstance(settings.api_key, SecretStr)
    assert settings.api_key.get_secret_value() == "sk-sentinel"
    assert (settings.base_url, settings.model) == ("https://ai.sentinel.example", "sentinel-model")


@pytest.mark.parametrize(("env_name", "attribute", "expected"), OPENAI_NAMES, ids=[row[0] for row in OPENAI_NAMES])
def test_configuration_settings_openai_table_name_reaches_field(
    monkeypatch: pytest.MonkeyPatch, env_name: str, attribute: str, expected: Any
) -> None:
    """The OPENAI__<FIELD> name sets the field; a fallback to the default would differ from the sentinel."""
    monkeypatch.setenv(env_name, str(expected))

    settings = OpenAISettings(_env_file=None)  # type: ignore[call-arg]

    assert getattr(settings, attribute) == expected


@pytest.mark.parametrize("env_name", OPENAI_RETIRED_NAMES)
def test_configuration_settings_openai_retired_name_is_unread(monkeypatch: pytest.MonkeyPatch, env_name: str) -> None:
    """The six old OPENAI_* names are read by no field: the slice builds exactly as without them."""
    baseline = OpenAISettings(_env_file=None).model_dump()  # type: ignore[call-arg]
    monkeypatch.setenv(env_name, "https://ai.retired.example" if env_name == "OPENAI_BASE_URL" else "7")

    settings = OpenAISettings(_env_file=None).model_dump()  # type: ignore[call-arg]

    assert settings == baseline


AWS_RETIRED_NAMES = [
    "AWS_SSO_SYSTEM_ADMIN_PERMISSIONS",
    "AWS_SSO_VIEW_ONLY_PERMISSIONS",
    "AWS_AUDIT_ACCOUNT_ROLE_ARN",
    "AWS_ORG_ACCOUNT_ROLE_ARN",
    "AWS_LOGGING_ACCOUNT_ROLE_ARN",
    "AWS_SSO_INSTANCE_ID",
    "AWS_SSO_INSTANCE_ARN",
    "AWS_RETRY_MAX_ATTEMPTS",
    "AWS_RETRY_MODE",
    "AWS_CONNECT_TIMEOUT_SECONDS",
    "AWS_READ_TIMEOUT_SECONDS",
    "AWS_TRANSIENT_RETRY_AFTER_SECONDS",
    "AWS_NOT_FOUND_CODES",
    "AWS_UNAUTHORIZED_CODES",
    "AWS_TRANSIENT_CODES",
]

AWS_NAMES: list[tuple[str, str, Any]] = [
    ("AWS__RETRY_MAX_ATTEMPTS", "retry_max_attempts", 5),
    ("AWS__RETRY_MODE", "retry_mode", "adaptive"),
    ("AWS__CONNECT_TIMEOUT_SECONDS", "connect_timeout_seconds", 4),
    ("AWS__READ_TIMEOUT_SECONDS", "read_timeout_seconds", 7),
    ("AWS__TRANSIENT_RETRY_AFTER_SECONDS", "transient_retry_after_seconds", 15),
]


@pytest.mark.parametrize(("env_name", "attribute", "expected"), AWS_NAMES, ids=[row[0] for row in AWS_NAMES])
def test_configuration_settings_aws_table_name_reaches_field(
    monkeypatch: pytest.MonkeyPatch, env_name: str, attribute: str, expected: Any
) -> None:
    """The AWS__<FIELD> name sets the field; a fallback to the default would differ from the sentinel."""
    monkeypatch.setenv(env_name, str(expected))

    settings = AWSSettings(_env_file=None)  # type: ignore[call-arg]

    assert getattr(settings, attribute) == expected


@pytest.mark.parametrize("env_name", AWS_RETIRED_NAMES)
def test_configuration_settings_aws_retired_name_is_unread(monkeypatch: pytest.MonkeyPatch, env_name: str) -> None:
    """The fifteen old AWS_* names are read by no field: the slices build exactly as without them."""
    baseline = (AWSSettings(_env_file=None).model_dump(), AccessPermissionSetsSettings(_env_file=None).model_dump())  # type: ignore[call-arg]
    monkeypatch.setenv(
        env_name, "7" if env_name.endswith(("SECONDS", "ATTEMPTS")) else "arn:aws:sso:::instance/ssoins-1234567890abcdef"
    )

    settings = (AWSSettings(_env_file=None).model_dump(), AccessPermissionSetsSettings(_env_file=None).model_dump())  # type: ignore[call-arg]

    assert settings == baseline


def test_configuration_settings_aws_tenant_names_build_the_tenant_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The five AWS__TENANT__ names reach the tenant entry; a fallback would leave it absent."""
    monkeypatch.setenv("AWS__TENANT__INSTANCE_ID", "d-1234567890")
    monkeypatch.setenv("AWS__TENANT__INSTANCE_ARN", "arn:aws:sso:::instance/ssoins-1234567890abcdef")
    monkeypatch.setenv("AWS__TENANT__AUDIT_ROLE_ARN", "arn:aws:iam::111111111111:role/sentinel-audit")
    monkeypatch.setenv("AWS__TENANT__ORG_ROLE_ARN", "arn:aws:iam::111111111111:role/sentinel-org")
    monkeypatch.setenv("AWS__TENANT__LOGGING_ROLE_ARN", "arn:aws:iam::111111111111:role/sentinel-logging")

    tenant = AWSSettings(_env_file=None).tenant  # type: ignore[call-arg]

    assert tenant is not None
    assert (tenant.instance_id, tenant.instance_arn) == ("d-1234567890", "arn:aws:sso:::instance/ssoins-1234567890abcdef")
    assert (tenant.audit_role_arn, tenant.org_role_arn, tenant.logging_role_arn) == (
        "arn:aws:iam::111111111111:role/sentinel-audit",
        "arn:aws:iam::111111111111:role/sentinel-org",
        "arn:aws:iam::111111111111:role/sentinel-logging",
    )


def test_configuration_settings_access_permission_sets_name_reaches_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ACCESS_PERMISSION_SETS__<FIELD> names set the two permission-set values."""
    monkeypatch.setenv("ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS", "SentinelAdmin")
    monkeypatch.setenv("ACCESS_PERMISSION_SETS__VIEW_ONLY_PERMISSIONS", "SentinelView")

    settings = AccessPermissionSetsSettings(_env_file=None)  # type: ignore[call-arg]

    assert (settings.system_admin_permissions, settings.view_only_permissions) == ("SentinelAdmin", "SentinelView")


def test_configuration_settings_no_slice_declares_an_sdk_aws_name() -> None:
    """The region and the endpoint are the SDK's: no AWS slice field is, or aliases, an AWS_* SDK name."""
    sdk_names = {"aws_region", "aws_default_region", "aws_endpoint_url_dynamodb", "dynamodb_endpoint_url", "region_name"}
    for slice_class in (AWSSettings, AccessPermissionSetsSettings):
        for name, field in slice_class.model_fields.items():
            assert name not in sdk_names
            assert not str(field.alias or "").upper().startswith("AWS_")


def test_configuration_settings_vendor_lower_case_names_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lower-case spelling of a Notify name is read too."""
    monkeypatch.setenv("notify__timeout_seconds", "23")

    notify = NotifySettings(_env_file=None)  # type: ignore[call-arg]

    assert notify.timeout_seconds == 23


def test_configuration_settings_spaced_env_file_lines_reach_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Lines written 'NAME =value', as some production .env lines are, reach a field."""
    monkeypatch.delenv("SENTINEL_SHARED_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SENTINEL_SHARED_KEY =spaced-shared-key\n")

    sentinel = SentinelSettings(_env_file=env_file)  # type: ignore[call-arg]

    assert sentinel.sentinel_shared_key == "spaced-shared-key"


def test_configuration_settings_identity_lower_case_environment_name_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lower-case spelling of ENVIRONMENT is read too."""
    monkeypatch.setenv("environment", "local")

    settings = IdentitySettings()

    assert settings.environment == "local"


def test_configuration_settings_identity_missing_environment_names_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing ENVIRONMENT fails validation and the error location is the field name."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        IdentitySettings()

    assert exc_info.value.errors()[0]["loc"] == ("environment",)


VENDOR_RETIRED_NAMES: list[tuple[type[BaseSettings], str]] = [
    (NotifySettings, "NOTIFY_SRE_USER_NAME"),
    (NotifySettings, "NOTIFY_SRE_CLIENT_SECRET"),
    (NotifySettings, "NOTIFY_API_URL"),
    (TrelloSettings, "TRELLO_APP_KEY"),
    (TrelloSettings, "TRELLO_TOKEN"),
    (TrelloSettings, "TRELLO_ATIP_BOARD"),
    (TrelloSettings, "TRELLO__APP_KEY"),
    (TrelloSettings, "TRELLO__TOKEN"),
    (OpsGenieSettings, "OPSGENIE_INTEGRATIONS_KEY"),
    (OpsGenieSettings, "OPSGENIE_KEY"),
    (MaxMindSettings, "MAXMIND_DB_PATH"),
    (MaxMindSettings, "MAXMIND_KEY"),
]


def test_configuration_settings_notify_names_configure_notify(monkeypatch: pytest.MonkeyPatch) -> None:
    """The two NOTIFY__ credentials reach their secret fields beside a tenant entry."""
    monkeypatch.setenv("NOTIFY__SRE_USER_NAME", "sentinel-user")
    monkeypatch.setenv("NOTIFY__SRE_CLIENT_SECRET", "sentinel-secret")
    monkeypatch.setenv("NOTIFY__TENANT__API_URL", "https://notify.sentinel.example")
    monkeypatch.setenv("NOTIFY__TIMEOUT_SECONDS", "17")

    settings = NotifySettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.sre_user_name.get_secret_value() == "sentinel-user"
    assert settings.sre_client_secret.get_secret_value() == "sentinel-secret"
    assert settings.tenant is not None
    assert settings.tenant.api_url == "https://notify.sentinel.example"
    assert settings.timeout_seconds == 17


def test_configuration_settings_opsgenie_names_configure_opsgenie(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPSGENIE__INTEGRATIONS_KEY reaches the secret field beside a tenant entry."""
    monkeypatch.setenv("OPSGENIE__INTEGRATIONS_KEY", "sentinel-opsgenie-key")
    monkeypatch.setenv("OPSGENIE__TENANT__API_URL", "https://api.eu.opsgenie.com")
    monkeypatch.setenv("OPSGENIE__TIMEOUT_SECONDS", "17")

    settings = OpsGenieSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.integrations_key.get_secret_value() == "sentinel-opsgenie-key"
    assert settings.tenant is not None
    assert settings.tenant.api_url == "https://api.eu.opsgenie.com"
    assert settings.timeout_seconds == 17


def test_configuration_settings_trello_names_configure_trello(monkeypatch: pytest.MonkeyPatch) -> None:
    """The two TRELLO__TENANT__ names build the tenant entry; TRELLO__ATIP_BOARD reaches the board."""
    monkeypatch.setenv("TRELLO__TENANT__APP_KEY", "sentinel-app-key")
    monkeypatch.setenv("TRELLO__TENANT__TOKEN", "sentinel-token")
    monkeypatch.setenv("TRELLO__ATIP_BOARD", "sentinel-board")

    settings = TrelloSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.tenant is not None
    assert settings.tenant.app_key.get_secret_value() == "sentinel-app-key"
    assert settings.tenant.token.get_secret_value() == "sentinel-token"
    assert settings.atip_board == "sentinel-board"


def test_configuration_settings_maxmind_name_configures_maxmind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAXMIND__TENANT__DATABASE_PATH", "/sentinel/GeoLite2.mmdb")

    tenant = MaxMindSettings(_env_file=None).tenant  # type: ignore[call-arg]

    assert tenant is not None
    assert tenant.database_path == "/sentinel/GeoLite2.mmdb"


@pytest.mark.parametrize(("settings_class", "env_name"), VENDOR_RETIRED_NAMES, ids=[row[1] for row in VENDOR_RETIRED_NAMES])
def test_configuration_settings_vendor_retired_name_is_unread(
    monkeypatch: pytest.MonkeyPatch, settings_class: type[BaseSettings], env_name: str
) -> None:
    """The old flat names are read by no field: the slice builds exactly as without them."""
    baseline = settings_class(_env_file=None).model_dump()  # type: ignore[call-arg]
    monkeypatch.setenv(env_name, "https://retired.example" if env_name.endswith("URL") else "retired")

    settings = settings_class(_env_file=None).model_dump()  # type: ignore[call-arg]

    assert settings == baseline
