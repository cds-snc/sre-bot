"""Shared access-domain config: runtime models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

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

    authn_token: str = "authn"  # noqa: S105 -- default group-slug token, not a credential
    authn_removal_mode: str = "delete"  # disable | delete | entitlement_only
    adapter_type: str = "fake"  # aws_identity_center | fake
    mode_overrides: dict[str, EntitlementMode] = field(default_factory=dict)


@dataclass(frozen=True)
class CatalogParserConfig:
    """Runtime configuration for a platform's catalog token parser."""

    known_envs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CatalogExtensions:
    """Typed runtime extensions for the catalog sub-feature."""

    parsers: dict[str, CatalogParserConfig] = field(default_factory=dict)
    platform_display_names: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EntitlementModeOverride:
    """Runtime per-group entitlement mode override record."""

    platform: str
    group_slug: str
    mode: EntitlementMode
    reason: str | None = None
    requested_by: str | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class AccessRuntimeConfig:
    """Fully-resolved runtime configuration shared across access sub-packages."""

    dir_prefix: str
    dir_separator: str = "-"
    platforms: dict[str, PlatformPolicy] = field(default_factory=dict)
    entitlement_mode_overrides: list[EntitlementModeOverride] = field(default_factory=list)
    # Typed extensions for catalog feature; empty dict when not present.
    extensions: dict[str, Any] = field(default_factory=dict)
    catalog_extensions: CatalogExtensions | None = None

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
    def catalog(self) -> CatalogExtensions | None:
        """Return typed catalog extension configuration."""
        return self.catalog_extensions


# This file contains only runtime domain models loaded from an external config
# document (JSON bundle, DynamoDB, etc.) — not from env vars.
# Feature settings live in packages.access.common.settings.AccessSettings.
