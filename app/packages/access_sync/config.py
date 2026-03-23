"""Access Sync runtime configuration models and config loader.

Runtime config is loaded from one external source selected by bootstrap settings
(ACCESS_SYNC_CONFIG_SOURCE).  This keeps per-group policy out of env vars and
allows changes without a code deploy.

Config loader sources:
  bundle   - Built-in default policy bundle defined in code.  Useful for local
             development and as a safe fallback.
  dynamodb - Load from a DynamoDB item (not yet implemented; reserved).
  s3       - Load from an S3 object (not yet implemented; reserved).
  ssm      - Load from an SSM parameter (not yet implemented; reserved).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional, Protocol

from infrastructure.operations import OperationResult
from packages.access_sync.policies import PlatformPolicy


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
    Contains all per-platform policies and optional runtime overrides.

    Infrastructure clients (AWS, Google Workspace, etc.) are obtained separately
    from infrastructure.services and come pre-configured with all needed bootstrap
    settings (e.g., AWS_SSO_INSTANCE_ID). Feature configuration is limited to
    policy definitions and per-group overrides.
    """

    policies: Dict[str, PlatformPolicy]
    entitlement_mode_overrides: List[EntitlementModeOverride] = field(
        default_factory=list
    )


class AccessSyncConfigLoader(Protocol):
    """Protocol for Access Sync config loaders.

    Each loader knows how to fetch and deserialise one runtime config document
    from its backing store.
    """

    def load(self, ref: str) -> OperationResult[AccessSyncRuntimeConfig]:
        """Load the runtime config identified by *ref*.

        Args:
            ref: Source-specific reference (table PK, S3 key, SSM path, bundle name).

        Returns:
            OperationResult[AccessSyncRuntimeConfig] — success with data, or error.
        """
        ...


class BundleConfigLoader:
    """Config loader that returns an empty bundle (no policies configured).

    Access Sync enters "waiting mode" when no policies are configured: no
    platforms are registered and sync_user returns POLICY_NOT_FOUND gracefully.
    Operators wire real policies via an external source (dynamodb / s3 / ssm).
    """

    def load(self, ref: str) -> OperationResult[AccessSyncRuntimeConfig]:
        """Return an empty bundle config with no pre-configured policies.

        Args:
            ref: Bundle name (ignored; kept for protocol compatibility).

        Returns:
            OperationResult with AccessSyncRuntimeConfig containing an empty
            policies dict. The feature will be in waiting mode until an
            external config source provides platform policies.
        """
        config = AccessSyncRuntimeConfig(policies={})
        return OperationResult.success(
            data=config,
            message=f"bundle_config_loaded ref={ref} policies=0 (waiting mode)",
        )


def get_access_sync_config_loader(source: str) -> AccessSyncConfigLoader:
    """Return the config loader for the given source string.

    Args:
        source: One of 'bundle', 'dynamodb', 's3', 'ssm'.

    Returns:
        An AccessSyncConfigLoader instance.

    Raises:
        NotImplementedError: For sources that are not yet implemented.
    """
    if source == "bundle":
        return BundleConfigLoader()

    raise NotImplementedError(
        f"Access Sync config source '{source}' is not yet implemented. "
        "Use ACCESS_SYNC_CONFIG_SOURCE=bundle for local development."
    )
