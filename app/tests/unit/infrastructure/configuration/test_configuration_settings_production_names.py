"""Each settings slice reads its deployment environment names into the named field.

Every row sets one environment variable to a sentinel that differs from the
field default and builds the slice from the process environment only, so a
field rename that silently stops reading its name falls back to the default and
fails here instead of in production. The names are the deploy interface: each
slice reads <SLICE>__<FIELD> beside its table, and a tenant entry from
<SLICE>__TENANT__<FIELD>. The security slice reads the configuration files and
is pinned by its own production-values test. The AWS region and the
dynamodb-local endpoint are the SDK's (AWS_DEFAULT_REGION,
AWS_ENDPOINT_URL_DYNAMODB), declared by no field. Names match case-insensitively,
and a dotenv line written 'NAME =value' still reaches a field.
"""

from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings

from features.cloud_operations.spending.settings import CloudOperationsSpendingSettings
from features.incident.common.settings import IncidentCoreSettings
from features.incident.postmortem.settings import IncidentPostmortemSettings
from features.incident.response.settings import IncidentResponseSettings
from features.talent.settings import TalentSettings
from integrations.aws.settings import AWSSettings
from integrations.google_workspace.settings import GoogleWorkspaceSettings
from integrations.maxmind.settings import MaxMindSettings
from integrations.notify.settings import NotifySettings
from integrations.openai.settings import OpenAISettings
from integrations.opsgenie.settings import OpsGenieSettings
from integrations.sentinel.settings import SentinelSettings
from integrations.slack.settings import SlackSettings
from integrations.trello.settings import TrelloSettings
from packages.access.common.settings import AccessPermissionSetsSettings
from server.configuration import IdentitySettings
from tests.factories.google_service_account import service_account_key

PRODUCTION_NAMES: list[tuple[type[BaseSettings], str, str, str, Any]] = [
    (IncidentCoreSettings, "INCIDENT_CORE__FOLDER_ID", "folder_id", "sentinel-id", "sentinel-id"),
    (IncidentCoreSettings, "INCIDENT_CORE__REPORT_TEMPLATE_ID", "report_template_id", "sentinel-id", "sentinel-id"),
    (IncidentCoreSettings, "INCIDENT_CORE__LIST_SHEET_ID", "list_sheet_id", "sentinel-id", "sentinel-id"),
    (IncidentResponseSettings, "INCIDENT_RESPONSE__HANDBOOK_ID", "handbook_id", "sentinel-id", "sentinel-id"),
    (IncidentPostmortemSettings, "INCIDENT_POSTMORTEM__CALENDAR_ID", "calendar_id", "sentinel-id", "sentinel-id"),
    (CloudOperationsSpendingSettings, "CLOUD_OPERATIONS_SPENDING__SHEET_ID", "sheet_id", "sentinel-id", "sentinel-id"),
    (TalentSettings, "TALENT__INTERNAL_FOLDER_ID", "internal_folder_id", "sentinel-id", "sentinel-id"),
    (TalentSettings, "TALENT__TEMPLATES_FOLDER_ID", "templates_folder_id", "sentinel-id", "sentinel-id"),
    (TalentSettings, "TALENT__SCORING_GUIDE_TEMPLATE_ID", "scoring_guide_template_id", "sentinel-id", "sentinel-id"),
    (TalentSettings, "TALENT__CORE_VALUES_INTERVIEW_NOTES_ID", "core_values_interview_notes_id", "sentinel-id", "sentinel-id"),
    (TalentSettings, "TALENT__TECHNICAL_INTERVIEW_NOTES_ID", "technical_interview_notes_id", "sentinel-id", "sentinel-id"),
    (TalentSettings, "TALENT__INTAKE_FORM_TEMPLATE_ID", "intake_form_template_id", "sentinel-id", "sentinel-id"),
    (TalentSettings, "TALENT__PHONE_SCREEN_TEMPLATE_ID", "phone_screen_template_id", "sentinel-id", "sentinel-id"),
    (
        TalentSettings,
        "TALENT__RECRUITMENT_FEEDBACK_TEMPLATE_ID",
        "recruitment_feedback_template_id",
        "sentinel-id",
        "sentinel-id",
    ),
    (TalentSettings, "TALENT__PANELIST_GUIDEBOOK_TEMPLATE_ID", "panelist_guidebook_template_id", "sentinel-id", "sentinel-id"),
    (SentinelSettings, "SENTINEL__CUSTOMER_ID", "customer_id", "sentinel-customer", "sentinel-customer"),
    (SentinelSettings, "SENTINEL__LOG_TYPE", "log_type", "SentinelLogs", "SentinelLogs"),
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
    monkeypatch.setenv("sentinel__log_type", "lower_sentinel")

    settings = SentinelSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.log_type == "lower_sentinel"


def test_configuration_settings_upper_case_keyword_accepted() -> None:
    """Constructor keywords in the environment spelling still set the lower-case field."""
    settings = SentinelSettings(_env_file=None, LOG_TYPE="UpperSentinel")  # type: ignore[call-arg]

    assert settings.log_type == "UpperSentinel"


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


GOOGLE_NAMES: list[tuple[str, str, str, Any]] = [
    ("GOOGLE_WORKSPACE__API_NUM_RETRIES", "api_num_retries", "7", 7),
    ("GOOGLE_WORKSPACE__API_TIMEOUT_SECONDS", "api_timeout_seconds", "12.5", 12.5),
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
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY", service_account_key())
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL", "bot@sentinel.example")

    tenant = GoogleWorkspaceSettings(_env_file=None).tenant  # type: ignore[call-arg]

    assert tenant is not None
    assert (tenant.customer_id, tenant.service_account_key, tenant.delegated_user_email) == (
        "C0sentinel",
        service_account_key(),
        "bot@sentinel.example",
    )


def test_configuration_settings_slack_and_google_lower_case_names_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lower-case spelling of a Slack name and of a Google name is read too."""
    monkeypatch.setenv("slack__tenant__team_id", "TSENTINEL1")
    monkeypatch.setenv("slack__bot_token", "xoxb-lower")
    monkeypatch.setenv("google_workspace__api_num_retries", "9")

    slack = SlackSettings(_env_file=None)  # type: ignore[call-arg]
    google = GoogleWorkspaceSettings(_env_file=None)  # type: ignore[call-arg]

    assert slack.bot_token == "xoxb-lower"
    assert google.api_num_retries == 9


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
    """Dotenv lines written 'NAME =value', with a space before the equals sign, reach a field."""
    monkeypatch.delenv("SENTINEL__SHARED_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SENTINEL__SHARED_KEY =spaced-shared-key\n")

    sentinel = SentinelSettings(_env_file=env_file)  # type: ignore[call-arg]

    assert sentinel.shared_key.get_secret_value() == "spaced-shared-key"


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
