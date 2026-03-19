"""Access Sync feature bootstrap settings.

Only contains env-var pointers for selecting the runtime config source.
All per-group, per-platform policy lives in the external runtime config document.
"""

from typing import Literal

from pydantic import Field

from infrastructure.configuration.base import FeatureSettings


class AccessSyncSettings(FeatureSettings):
    """Bootstrap settings for Access Sync runtime config loading.

    Environment Variables:
        ACCESS_SYNC_CONFIG_SOURCE: Where to load runtime config from
            (bundle | dynamodb | s3 | ssm).  Default: bundle.
        ACCESS_SYNC_CONFIG_REF: Reference key for the config document
            (table row PK, S3 key, SSM path, or bundle name).
        ACCESS_SYNC_CONFIG_REFRESH_SECONDS: How often to refresh runtime
            config in seconds (reserved for future cache invalidation).
    """

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
