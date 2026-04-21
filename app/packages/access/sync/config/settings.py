"""Access Sync bootstrap settings and compatibility aliases.

AccessSyncSettings reads env vars that select the runtime config source and
control feature flags.

Runtime domain models were moved to ``packages.access.common.config`` and are
re-exported here for compatibility during the transition.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.access.common.config import (
    AccessRuntimeConfig,
    EntitlementModeOverride as CommonEntitlementModeOverride,
)


# ---------------------------------------------------------------------------
# Bootstrap Settings
# ---------------------------------------------------------------------------
class AccessSyncSettings(BaseSettings):
    """Bootstrap settings for Access Sync runtime config loading.

    Environment Variables:
        ACCESS_SYNC_ENABLED: Master on/off switch. Default: false.
        ACCESS_CONFIG_SOURCE: Where to load runtime config from
            (bundle | inline_json | file_json | dynamodb | s3 | ssm). Default: bundle.
        ACCESS_CONFIG_REF: Reference key for the config document
            (table row PK, S3 key, SSM path, or bundle name).
        ACCESS_SYNC_CONFIG_REFRESH_SECONDS: How often to refresh runtime
            config in seconds (reserved for future cache invalidation).
        ACCESS_SYNC_RECONCILIATION_ENABLED: Enable scheduled full-platform
            sync. Default: false.
        ACCESS_SYNC_RECONCILIATION_SCHEDULE: Daily sync run time in "HH:MM"
            format (UTC). Default: "03:00".
    """

    enabled: bool = Field(
        default=False,
        alias="ACCESS_SYNC_ENABLED",
    )
    config_source: Literal[
        "bundle", "inline_json", "file_json", "env", "dynamodb", "s3", "ssm"
    ] = Field(
        default="bundle",
        alias="ACCESS_CONFIG_SOURCE",
    )
    config_ref: str = Field(
        default="default",
        alias="ACCESS_CONFIG_REF",
    )
    config_refresh_seconds: int = Field(
        default=300,
        alias="ACCESS_SYNC_CONFIG_REFRESH_SECONDS",
        # NOTE: This setting is declared for future use. The current provider
        # pattern caches config permanently for the process lifetime. To pick
        # up a config change, restart the process.
    )
    reconciliation_enabled: bool = Field(
        default=False,
        alias="ACCESS_SYNC_RECONCILIATION_ENABLED",
    )
    reconciliation_schedule: str = Field(
        default="03:00",
        alias="ACCESS_SYNC_RECONCILIATION_SCHEDULE",
    )
    sync_job_ttl_seconds: int = Field(
        default=86400,
        alias="ACCESS_SYNC_JOB_TTL_SECONDS",
        description="How long completed/failed sync job records are retained (seconds). Default: 24h.",
    )
    sync_lock_stale_after_seconds: int = Field(
        default=14400,
        alias="ACCESS_SYNC_LOCK_STALE_SECONDS",
        description="Running lock older than this is treated as stale (crashed thread). Default: 4h.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


# ---------------------------------------------------------------------------
# Compatibility aliases (transition)
# ---------------------------------------------------------------------------
AccessSyncRuntimeConfig = AccessRuntimeConfig
EntitlementModeOverride = CommonEntitlementModeOverride
