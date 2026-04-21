"""Shared access-domain config: runtime models and bootstrap settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.access.common.naming import AccessGroupNaming


EntitlementMode = Literal["sync_managed", "ephemeral", "deactivated"]


@dataclass(frozen=True)
class EntitlementRule:
    """Runtime binding of an IDP group slug to one platform entitlement."""

    group_slug: str
    entitlement_id: str
    entitlement_type: str = "group"
    mode: EntitlementMode = "sync_managed"


@dataclass(frozen=True)
class PlatformPolicy:
    """Per-platform policy loaded from runtime configuration."""

    authn_token: str = "authn"
    authn_removal_mode: str = "delete"  # disable | delete | entitlement_only
    adapter_type: str = "fake"  # aws_identity_center | fake
    mode_overrides: Dict[str, EntitlementMode] = field(default_factory=dict)


@dataclass(frozen=True)
class EntitlementModeOverride:
    """Runtime per-group entitlement mode override record."""

    platform: str
    group_slug: str
    mode: EntitlementMode
    reason: Optional[str] = None
    requested_by: Optional[str] = None
    expires_at: Optional[datetime] = None


@dataclass(frozen=True)
class AccessRuntimeConfig:
    """Fully-resolved runtime configuration shared across access sub-packages."""

    dir_prefix: str
    dir_separator: str = "-"
    platforms: Dict[str, PlatformPolicy] = field(default_factory=dict)
    entitlement_mode_overrides: List[EntitlementModeOverride] = field(
        default_factory=list
    )
    # Optional extension bag for package-specific read-only configuration.
    extensions: Dict[str, Any] = field(default_factory=dict)

    def group_prefix(self, platform: str) -> str:
        """Return the IDP group slug prefix for a given platform."""
        return AccessGroupNaming(
            dir_prefix=self.dir_prefix,
            dir_separator=self.dir_separator,
        ).group_prefix(platform)

    def authn_group_slug(self, platform: str) -> str:
        """Return the full authn group slug for a given platform."""
        return AccessGroupNaming(
            dir_prefix=self.dir_prefix,
            dir_separator=self.dir_separator,
        ).authn_group_slug(
            platform=platform,
            authn_token=self.platforms[platform].authn_token,
        )

    @property
    def catalog(self) -> Optional[Any]:
        """Return optional catalog extension configuration."""
        value = self.extensions.get("catalog")
        return value


# ---------------------------------------------------------------------------
# Bootstrap Settings — which source/ref to load AccessRuntimeConfig from
# ---------------------------------------------------------------------------


class AccessConfigBootstrapSettings(BaseSettings):
    """Domain-wide bootstrap: selects how AccessRuntimeConfig is loaded.

    These settings apply to the entire access feature (sync, catalog, request).
    They are intentionally separated from sync-specific operational settings.

    Environment Variables:
        ACCESS_CONFIG_SOURCE: Where to load runtime config from
            (bundle | inline_json | file_json | env | dynamodb | s3 | ssm).
            Default: bundle.
        ACCESS_CONFIG_REF: Reference key for the config document
            (table row PK, S3 key, SSM path, inline JSON, or bundle name).
            Default: default.
        ACCESS_CONFIG_REFRESH_SECONDS: Reserved for future cache invalidation.
            Default: 300.
    """

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
        alias="ACCESS_CONFIG_REFRESH_SECONDS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )
