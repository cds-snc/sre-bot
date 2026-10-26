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
are pinned as unread; production still sets GOOGLE_RESOURCES. The AWS, OpenAI, Notify, Trello, OpsGenie,
MaxMind and Sentinel slices likewise: production sets the AWS_*_ACCOUNT_ROLE_ARN
names (only AWS_ORG_ACCOUNT_ROLE_ARN with a value), the AWS_SSO_* names,
OPENAI_API_KEY, NOTIFY_SRE_USER_NAME, NOTIFY_SRE_CLIENT_SECRET, NOTIFY_API_URL,
the TRELLO_* names, OPSGENIE_INTEGRATIONS_KEY and the SENTINEL_* names, some of
them written 'NAME =value' in the .env file; AWS_REGION is injected by the
platform, and the remaining names stay part of the interface. The identity,
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
from infrastructure.configuration.infrastructure.retry import RetrySettings
from infrastructure.coordination.settings import ConditionalWriteSettings
from infrastructure.directory.settings import DirectorySettings
from infrastructure.drive.settings import DriveSettings
from infrastructure.spreadsheets.settings import SpreadsheetSettings
from integrations.aws.settings import AWSSettings
from integrations.google_workspace.settings import GoogleResourcesConfig, GoogleWorkspaceSettings
from integrations.maxmind.settings import MaxMindSettings
from integrations.notify.settings import NotifySettings
from integrations.openai.settings import OpenAISettings
from integrations.opsgenie.settings import OpsGenieSettings
from integrations.sentinel.settings import SentinelSettings
from integrations.slack.settings import SlackSettings
from integrations.trello.settings import TrelloSettings
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
    (RetrySettings, "RETRY_ENABLED", "enabled", "false", False),
    (RetrySettings, "RETRY_BACKEND", "backend", "dynamodb", "dynamodb"),
    (RetrySettings, "RETRY_DYNAMODB_TABLE_NAME", "dynamodb_table_name", "sentinel-retry", "sentinel-retry"),
    (RetrySettings, "RETRY_DYNAMODB_TTL_DAYS", "dynamodb_ttl_days", "9", 9),
    (RetrySettings, "RETRY_MAX_ATTEMPTS", "max_attempts", "8", 8),
    (RetrySettings, "RETRY_BASE_DELAY_SECONDS", "base_delay_seconds", "61", 61),
    (RetrySettings, "RETRY_MAX_DELAY_SECONDS", "max_delay_seconds", "3601", 3601),
    (RetrySettings, "RETRY_BATCH_SIZE", "batch_size", "11", 11),
    (RetrySettings, "RETRY_CLAIM_LEASE_SECONDS", "claim_lease_seconds", "301", 301),
    (DirectorySettings, "DIRECTORY_PROVIDER", "provider", "entra_id", "entra_id"),
    (DirectorySettings, "DIRECTORY_REQUIRE_STARTUP_WARMUP", "require_startup_warmup", "true", True),
    (DirectorySettings, "DIRECTORY_CACHE_TTL_SECONDS", "cache_ttl_seconds", "61", 61),
    (DirectorySettings, "DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS", "startup_warmup_timeout_seconds", "3", 3),
    (
        GoogleResourcesConfig,
        "GOOGLE_RESOURCES",
        "resources",
        '{"inc":{"d":"sentinel-drive"}}',
        {"inc": {"d": "sentinel-drive"}},
    ),
    (
        AWSSettings,
        "AWS_AUDIT_ACCOUNT_ROLE_ARN",
        "audit_role_arn",
        "arn:aws:iam::111111111111:role/sentinel-audit",
        "arn:aws:iam::111111111111:role/sentinel-audit",
    ),
    (
        AWSSettings,
        "AWS_LOGGING_ACCOUNT_ROLE_ARN",
        "logging_role_arn",
        "arn:aws:iam::111111111111:role/sentinel-logging",
        "arn:aws:iam::111111111111:role/sentinel-logging",
    ),
    (
        AWSSettings,
        "AWS_ORG_ACCOUNT_ROLE_ARN",
        "org_role_arn",
        "arn:aws:iam::111111111111:role/sentinel-org",
        "arn:aws:iam::111111111111:role/sentinel-org",
    ),
    (
        AWSSettings,
        "AWS_SSO_INSTANCE_ARN",
        "instance_arn",
        "arn:aws:sso:::instance/ssoins-sentinel",
        "arn:aws:sso:::instance/ssoins-sentinel",
    ),
    (AWSSettings, "AWS_SSO_INSTANCE_ID", "instance_id", "d-sentinel", "d-sentinel"),
    (AWSSettings, "AWS_SSO_SYSTEM_ADMIN_PERMISSIONS", "system_admin_permissions", "SentinelAdmin", "SentinelAdmin"),
    (AWSSettings, "AWS_SSO_VIEW_ONLY_PERMISSIONS", "view_only_permissions", "SentinelView", "SentinelView"),
    (AWSSettings, "AWS_REGION", "aws_region", "sentinel-region-1", "sentinel-region-1"),
    (
        AWSSettings,
        "AWS_ENDPOINT_URL_DYNAMODB",
        "dynamodb_endpoint_url",
        "http://sentinel-dynamodb:8000",
        "http://sentinel-dynamodb:8000",
    ),
    (AWSSettings, "AWS_RETRY_MAX_ATTEMPTS", "retry_max_attempts", "5", 5),
    (AWSSettings, "AWS_RETRY_MODE", "retry_mode", "adaptive", "adaptive"),
    (AWSSettings, "AWS_CONNECT_TIMEOUT_SECONDS", "connect_timeout_seconds", "4", 4),
    (AWSSettings, "AWS_READ_TIMEOUT_SECONDS", "read_timeout_seconds", "7", 7),
    (AWSSettings, "AWS_TRANSIENT_RETRY_AFTER_SECONDS", "transient_retry_after_seconds", "15", 15),
    (AWSSettings, "AWS_NOT_FOUND_CODES", "not_found_codes", '["SentinelMissing"]', ["SentinelMissing"]),
    (AWSSettings, "AWS_UNAUTHORIZED_CODES", "unauthorized_codes", '["SentinelDenied"]', ["SentinelDenied"]),
    (AWSSettings, "AWS_TRANSIENT_CODES", "transient_codes", '["SentinelBusy"]', ["SentinelBusy"]),
    (NotifySettings, "NOTIFY_SRE_USER_NAME", "notify_sre_user_name", "sentinel-user", "sentinel-user"),
    (NotifySettings, "NOTIFY_SRE_CLIENT_SECRET", "notify_sre_client_secret", "sentinel-secret", "sentinel-secret"),
    (
        NotifySettings,
        "NOTIFY_API_URL",
        "notify_api_url",
        "https://notify.sentinel.example",
        "https://notify.sentinel.example",
    ),
    (TrelloSettings, "TRELLO_APP_KEY", "trello_app_key", "sentinel-app-key", "sentinel-app-key"),
    (TrelloSettings, "TRELLO_TOKEN", "trello_token", "sentinel-token", "sentinel-token"),
    (TrelloSettings, "TRELLO_ATIP_BOARD", "trello_atip_board", "sentinel-board", "sentinel-board"),
    (
        OpsGenieSettings,
        "OPSGENIE_INTEGRATIONS_KEY",
        "opsgenie_integrations_key",
        "sentinel-opsgenie-key",
        "sentinel-opsgenie-key",
    ),
    (MaxMindSettings, "MAXMIND_DB_PATH", "maxmind_db_path", "/sentinel/GeoLite2.mmdb", "/sentinel/GeoLite2.mmdb"),
    (SentinelSettings, "SENTINEL_CUSTOMER_ID", "sentinel_customer_id", "sentinel-customer", "sentinel-customer"),
    (SentinelSettings, "SENTINEL_LOG_TYPE", "sentinel_log_type", "SentinelLogs", "SentinelLogs"),
    (SentinelSettings, "SENTINEL_SHARED_KEY", "sentinel_shared_key", "sentinel-shared-key", "sentinel-shared-key"),
    (IdentitySettings, "ENVIRONMENT", "environment", "production", "production"),
    (IdentitySettings, "GIT_SHA", "git_sha", "sentinel-sha", "sentinel-sha"),
]

_OPENAI_COMPANION_KEY = "sk-companion"
"""OPENAI_API_KEY is required, so every OpenAI row sets it beside the name under test."""

OPENAI_NAMES: list[tuple[str, str, str, Any]] = [
    ("OPENAI_MODEL", "model", "sentinel-model", "sentinel-model"),
    ("OPENAI_MAX_OUTPUT_TOKENS", "max_output_tokens", "1234", 1234),
    ("OPENAI_TEMPERATURE", "temperature", "0.25", 0.25),
    ("OPENAI_TIMEOUT_SECONDS", "timeout_seconds", "42.5", 42.5),
    ("OPENAI_BASE_URL", "base_url", "https://ai.sentinel.example", "https://ai.sentinel.example"),
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


@pytest.mark.parametrize(
    ("settings_class", "env_name"),
    [(DriveSettings, "DRIVE_PROVIDER"), (SpreadsheetSettings, "SPREADSHEET_PROVIDER")],
)
def test_configuration_settings_single_value_provider_name_is_read(
    monkeypatch: pytest.MonkeyPatch,
    settings_class: type[BaseSettings],
    env_name: str,
) -> None:
    """The provider allows only its default, so an unknown value is rejected, proving the name is read."""
    monkeypatch.setenv(env_name, "sentinel")

    with pytest.raises(ValidationError):
        settings_class(_env_file=None)  # type: ignore[call-arg]


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


def test_configuration_settings_openai_api_key_reaches_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPENAI_API_KEY sets the required secret field; compared through its secret value."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sentinel")

    settings = OpenAISettings(_env_file=None)  # type: ignore[call-arg]

    assert isinstance(settings.api_key, SecretStr)
    assert settings.api_key.get_secret_value() == "sk-sentinel"


@pytest.mark.parametrize(
    ("env_name", "attribute", "raw", "expected"),
    OPENAI_NAMES,
    ids=[row[0] for row in OPENAI_NAMES],
)
def test_configuration_settings_openai_name_reaches_field(
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    attribute: str,
    raw: str,
    expected: Any,
) -> None:
    """Each OpenAI name sets its field when the required key is present; a default would differ from the sentinel."""
    monkeypatch.setenv("OPENAI_API_KEY", _OPENAI_COMPANION_KEY)
    monkeypatch.setenv(env_name, raw)

    settings = OpenAISettings(_env_file=None)  # type: ignore[call-arg]

    assert getattr(settings, attribute) == expected


def test_configuration_settings_aws_org_role_only_maps_services(monkeypatch: pytest.MonkeyPatch) -> None:
    """With only the org role set, as in production, the org-role services get it and the audit and logging roles stay empty."""
    org_role = "arn:aws:iam::111111111111:role/sentinel-org"
    monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", org_role)
    monkeypatch.delenv("AWS_AUDIT_ACCOUNT_ROLE_ARN", raising=False)
    monkeypatch.delenv("AWS_LOGGING_ACCOUNT_ROLE_ARN", raising=False)

    role_map = AWSSettings(_env_file=None).service_role_map  # type: ignore[call-arg]

    for service in ("organizations", "identitystore", "sso-admin", "ce"):
        assert role_map[service] == org_role
    assert role_map["audit"] == ""
    assert role_map["logging"] == ""


def test_configuration_settings_vendor_lower_case_names_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lower-case spelling of a Notify name and of an AWS alias is read too."""
    monkeypatch.setenv("notify_api_url", "https://lower.sentinel.example")
    monkeypatch.setenv("aws_retry_mode", "adaptive")

    notify = NotifySettings(_env_file=None)  # type: ignore[call-arg]
    aws = AWSSettings(_env_file=None)  # type: ignore[call-arg]

    assert notify.notify_api_url == "https://lower.sentinel.example"
    assert aws.retry_mode == "adaptive"


def test_configuration_settings_aws_bare_field_name_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bare field name RETRY_MODE is not an environment name; only the AWS_RETRY_MODE alias is."""
    monkeypatch.setenv("RETRY_MODE", "legacy")
    monkeypatch.delenv("AWS_RETRY_MODE", raising=False)

    settings = AWSSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.retry_mode == "standard"


def test_configuration_settings_aws_upper_case_keyword_accepted() -> None:
    """A constructor keyword in the environment spelling still sets the lower-case AWS field."""
    settings = AWSSettings(_env_file=None, AWS_REGION="kw-region")  # type: ignore[call-arg]

    assert settings.aws_region == "kw-region"


def test_configuration_settings_spaced_env_file_lines_reach_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Lines written 'NAME =value', as some production .env lines are, reach a no-alias and an aliased field."""
    monkeypatch.delenv("SENTINEL_SHARED_KEY", raising=False)
    monkeypatch.delenv("AWS_SSO_INSTANCE_ID", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SENTINEL_SHARED_KEY =spaced-shared-key\nAWS_SSO_INSTANCE_ID =d-spaced\n")

    sentinel = SentinelSettings(_env_file=env_file)  # type: ignore[call-arg]
    aws = AWSSettings(_env_file=env_file)  # type: ignore[call-arg]

    assert sentinel.sentinel_shared_key == "spaced-shared-key"
    assert aws.instance_id == "d-spaced"


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
