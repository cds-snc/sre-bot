"""Access Sync bootstrap settings.

Only contains env-var pointers for selecting the runtime config source
and feature-level on/off switches. All per-group, per-platform policy
lives in the external runtime config document selected by config_source.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AccessSyncSettings(BaseSettings):
    """Bootstrap settings for Access Sync runtime config loading.

    Environment Variables:
        ACCESS_SYNC_ENABLED: Master on/off switch. Default: false.
        ACCESS_SYNC_CONFIG_SOURCE: Where to load runtime config from
            (bundle | dynamodb | s3 | ssm). Default: bundle.
        ACCESS_SYNC_CONFIG_REF: Reference key for the config document
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
    config_source: Literal["bundle", "dynamodb", "s3", "ssm"] = Field(
        default="bundle",
        alias="ACCESS_SYNC_CONFIG_SOURCE",
    )
    config_ref: str = Field(
        default="default",
        alias="ACCESS_SYNC_CONFIG_REF",
    )
    config_refresh_seconds: int = Field(
        default=300,
        alias="ACCESS_SYNC_CONFIG_REFRESH_SECONDS",
    )
    reconciliation_enabled: bool = Field(
        default=False,
        alias="ACCESS_SYNC_RECONCILIATION_ENABLED",
    )
    reconciliation_schedule: str = Field(
        default="03:00",
        alias="ACCESS_SYNC_RECONCILIATION_SCHEDULE",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )
