"""Each settings slice reads its deployment environment names into the named field.

Every row sets one environment variable to a sentinel that differs from the
field default and builds the slice from the process environment only, so a
field rename that silently stops reading its name falls back to the default and
fails here instead of in production. The names are the deploy interface: in
production ISSUER_CONFIG (from the SSM-delivered .env file) and
CORS_ALLOWED_ORIGINS (from the task definition) are set; the other names run on
their defaults today but stay part of the interface.
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
from infrastructure.security.settings import SecuritySettings
from infrastructure.spreadsheets.settings import SpreadsheetSettings
from jobs.settings import SchedulerSettings

_ISSUER_SENTINEL = (
    '{"https://issuer.sentinel.example":{"jwks_uri":"https://issuer.sentinel.example/jwks",'
    '"algorithms":["ES256"],"audience":"sentinel-audience"}}'
)

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
    (SchedulerSettings, "DEFAULT_TIER2_LEASE_TTL_SECONDS", "default_tier2_lease_ttl_seconds", "777", 777),
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
        SecuritySettings,
        "ISSUER_CONFIG",
        "issuer_config",
        _ISSUER_SENTINEL,
        {
            "https://issuer.sentinel.example": {
                "jwks_uri": "https://issuer.sentinel.example/jwks",
                "algorithms": ["ES256"],
                "audience": "sentinel-audience",
            }
        },
    ),
    (
        SecuritySettings,
        "CORS_ALLOWED_ORIGINS",
        "cors_allowed_origins",
        '["https://sentinel.example"]',
        ["https://sentinel.example"],
    ),
    (SecuritySettings, "CORS_ALLOWED_METHODS", "cors_allowed_methods", '["PUT"]', ["PUT"]),
    (SecuritySettings, "CORS_ALLOWED_HEADERS", "cors_allowed_headers", '["X-Sentinel"]', ["X-Sentinel"]),
    (SecuritySettings, "DEV_BYPASS_ENABLED", "dev_bypass_enabled", "true", True),
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


def test_configuration_settings_dev_bypass_token_reaches_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """DEV_BYPASS_TOKEN sets the secret field; compared through its secret value."""
    monkeypatch.setenv("DEV_BYPASS_TOKEN", "sentinel-token")

    settings = SecuritySettings(_env_file=None)  # type: ignore[call-arg]

    assert isinstance(settings.dev_bypass_token, SecretStr)
    assert settings.dev_bypass_token.get_secret_value() == "sentinel-token"


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


def test_configuration_settings_production_empty_cors_origins_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deployed CORS_ALLOWED_ORIGINS value, an encoded empty list, parses to no origins."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "[]")

    settings = SecuritySettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.cors_allowed_origins == []


def test_configuration_settings_issuer_config_read_from_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ISSUER_CONFIG written to a .env file, as production delivers it, reaches the field."""
    monkeypatch.delenv("ISSUER_CONFIG", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(f"ISSUER_CONFIG='{_ISSUER_SENTINEL}'\n")

    settings = SecuritySettings(_env_file=env_file)  # type: ignore[call-arg]

    assert settings.issuer_config is not None
    assert list(settings.issuer_config) == ["https://issuer.sentinel.example"]


def test_configuration_settings_lower_case_environment_name_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Names match case-insensitively, so the lower-case spelling of a name is read too."""
    monkeypatch.setenv("audit_table_name", "lower_sentinel")

    settings = AuditSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.audit_table_name == "lower_sentinel"


def test_configuration_settings_upper_case_keyword_accepted() -> None:
    """Constructor keywords in the environment spelling still set the lower-case field."""
    settings = ConditionalWriteSettings(_env_file=None, IDEMPOTENCY_TTL_SECONDS=42)  # type: ignore[call-arg]

    assert settings.idempotency_ttl_seconds == 42
