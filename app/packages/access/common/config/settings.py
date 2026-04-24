"""Shared access-domain config: runtime models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

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


# This file contains only runtime domain models loaded from an external config
# document (JSON bundle, DynamoDB, etc.) — not from env vars.
# Feature settings live in packages.access.common.settings.AccessSettings.
