"""Access Sync bootstrap settings and runtime domain models.

AccessSyncSettings reads env vars that select the runtime config source and
control feature flags.

Runtime domain models (AccessSyncRuntimeConfig, EntitlementModeOverride) live
here because they depend only on policies.py and stdlib — no loader logic needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.access_sync.policies import PlatformPolicy


# ---------------------------------------------------------------------------
# Bootstrap Settings
# ---------------------------------------------------------------------------
class AccessSyncSettings(BaseSettings):
    """Bootstrap settings for Access Sync runtime config loading.

    Environment Variables:
        ACCESS_SYNC_ENABLED: Master on/off switch. Default: false.
        ACCESS_SYNC_CONFIG_SOURCE: Where to load runtime config from
            (bundle | inline_json | file_json | dynamodb | s3 | ssm). Default: bundle.
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
    config_source: Literal[
        "bundle", "inline_json", "file_json", "env", "dynamodb", "s3", "ssm"
    ] = Field(
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

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


# ---------------------------------------------------------------------------
# Runtime Domain Models
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EntitlementModeOverride:
    """Runtime per-group entitlement mode override record.

    Written by Access Sync Admin and consumed by the runtime config loader to
    amend the effective mode of individual entitlement groups at runtime without
    code deploys.
    """

    platform: str
    group_slug: str
    mode: Literal["sync_managed", "ephemeral", "deactivated"]
    reason: Optional[str] = None
    requested_by: Optional[str] = None
    expires_at: Optional[datetime] = None


@dataclass(frozen=True)
class AccessSyncRuntimeConfig:
    """Fully-resolved runtime configuration for Access Sync.

    Loaded once at startup via the config loader selected by bootstrap settings.
    Contains the organization-wide group naming convention and per-platform
    policies.  Slug construction -- platform prefix, authn group slug -- is
    derived from ``dir_prefix``, ``dir_separator``, and the per-platform
    ``PlatformPolicy.authn_token`` rather than stored explicitly.

    Infrastructure clients (AWS, Google Workspace, etc.) are obtained separately
    from infrastructure.services and come pre-configured with all needed bootstrap
    settings (e.g., AWS_SSO_INSTANCE_ID). Feature configuration is limited to
    group naming and policy definitions.
    """

    dir_prefix: str
    dir_separator: str = "-"
    platforms: Dict[str, PlatformPolicy] = field(default_factory=dict)
    entitlement_mode_overrides: List[EntitlementModeOverride] = field(
        default_factory=list
    )

    def group_prefix(self, platform: str) -> str:
        """Return the IDP group slug prefix for a given platform.

        Example: dir_prefix="sg", dir_separator="-", platform="aws" -> "sg-aws-".
        """
        return f"{self.dir_prefix}{self.dir_separator}{platform}{self.dir_separator}"

    def authn_group_slug(self, platform: str) -> str:
        """Return the full authn group slug for a given platform.

        Example: "sg-aws-authn" when authn_token="authn".
        """
        return f"{self.group_prefix(platform)}{self.platforms[platform].authn_token}"
