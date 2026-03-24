"""Access Sync bootstrap settings and runtime configuration.

AccessSyncSettings reads env vars that select the runtime config source and
control feature flags. Runtime config is loaded from the selected external
source, keeping per-group policy out of env vars so policies can change without
a code deploy.

Config loader sources:
    bundle   - Built-in empty bundle. Default for local development.
    inline_json - Parse ACCESS_SYNC_CONFIG_REF as inline JSON text.
    file_json - Read ACCESS_SYNC_CONFIG_REF as a path to a local JSON file.
    dynamodb - Load from a DynamoDB item (reserved; not yet implemented).
    s3       - Load from an S3 object (reserved; not yet implemented).
    ssm      - Load from an SSM parameter (reserved; not yet implemented).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional, Protocol

from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.policies import EntitlementRule, PlatformPolicy


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
        "bundle", "inline_json", "file_json", "dynamodb", "s3", "ssm"
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


# ---------------------------------------------------------------------------
# Runtime Config Input Models (JSON)
# ---------------------------------------------------------------------------
class EntitlementRuleConfigModel(BaseModel):
    """Typed schema for one entitlement rule in runtime config JSON."""

    group_slug: str
    entitlement_type: str
    entitlement_id: str
    mode: str = "sync_managed"


class PlatformPolicyConfigModel(BaseModel):
    """Typed schema for one platform policy in runtime config JSON."""

    platform: str
    authn_group_slug: str
    authn_mode: str
    authn_removal_mode: str
    entitlement_rules: List[EntitlementRuleConfigModel] = Field(default_factory=list)


class RuntimeConfigJsonSettings(BaseSettings):
    """Settings model used with JsonConfigSettingsSource for file-based configs."""

    policies: Dict[str, PlatformPolicyConfigModel] = Field(default_factory=dict)

    model_config = SettingsConfigDict(
        extra="ignore",
    )


# ---------------------------------------------------------------------------
# Loader Contract + Shared Conversion
# ---------------------------------------------------------------------------
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


def _build_runtime_config(
    policies_model: Dict[str, PlatformPolicyConfigModel],
) -> AccessSyncRuntimeConfig:
    """Convert validated JSON policy models into AccessSyncRuntimeConfig."""
    policies: Dict[str, PlatformPolicy] = {}

    for fallback_key, raw_policy in policies_model.items():
        entitlement_rules: List[EntitlementRule] = []
        for rule in raw_policy.entitlement_rules:
            entitlement_rules.append(
                EntitlementRule(
                    group_slug=rule.group_slug,
                    entitlement_type=rule.entitlement_type,
                    entitlement_id=rule.entitlement_id,
                    mode=rule.mode,
                )
            )

        policy = PlatformPolicy(
            platform=raw_policy.platform,
            authn_group_slug=raw_policy.authn_group_slug,
            authn_mode=raw_policy.authn_mode,
            authn_removal_mode=raw_policy.authn_removal_mode,
            entitlement_rules=entitlement_rules,
        )
        policies[str(policy.platform or fallback_key)] = policy

    return AccessSyncRuntimeConfig(policies=policies)


def _validate_runtime_config_payload(
    payload: object,
    error_prefix: str,
) -> OperationResult[AccessSyncRuntimeConfig]:
    """Validate parsed JSON payload and build runtime config."""
    try:
        validated = RuntimeConfigJsonSettings.model_validate(payload)
    except ValidationError as exc:
        return OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message=f"{error_prefix}_invalid_policy: {exc}",
            error_code="CONFIG_INVALID_SHAPE",
        )

    config = _build_runtime_config(validated.policies)
    return OperationResult.success(
        data=config,
        message=f"{error_prefix}_loaded policies={len(config.policies)}",
    )


# ---------------------------------------------------------------------------
# Config Loaders
# ---------------------------------------------------------------------------
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


class InlineJsonConfigLoader:
    """Config loader that parses runtime policy from ACCESS_SYNC_CONFIG_REF JSON."""

    def load(self, ref: str) -> OperationResult[AccessSyncRuntimeConfig]:
        """Parse *ref* as JSON and build AccessSyncRuntimeConfig.

        Expected shape:
            {
              "policies": {
                "aws": {
                  "platform": "aws",
                  "authn_group_slug": "sg-aws-authn",
                  "authn_mode": "derived",
                  "authn_removal_mode": "delete",
                  "entitlement_rules": []
                }
              }
            }
        """
        try:
            payload = json.loads(ref)
        except json.JSONDecodeError as exc:
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message=f"inline_json_config_invalid_json: {exc.msg}",
                error_code="CONFIG_INVALID_JSON",
            )
        return _validate_runtime_config_payload(
            payload=payload,
            error_prefix="inline_json_config",
        )


class FileJsonConfigLoader:
    """Config loader that parses runtime policy from a JSON file path in ref."""

    def load(self, ref: str) -> OperationResult[AccessSyncRuntimeConfig]:
        """Read *ref* as a JSON file path and build AccessSyncRuntimeConfig."""
        path = Path(ref)
        if not path.exists():
            return OperationResult.error(
                status=OperationStatus.NOT_FOUND,
                message=f"file_json_config_not_found: {path}",
                error_code="CONFIG_NOT_FOUND",
            )
        if not path.is_file():
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message=f"file_json_config_invalid_path: not a file: {path}",
                error_code="CONFIG_INVALID_SHAPE",
            )

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            return OperationResult.error(
                status=OperationStatus.TRANSIENT_ERROR,
                message=f"file_json_config_read_failed: {exc}",
                error_code="CONFIG_READ_FAILED",
            )
        except json.JSONDecodeError as exc:
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message=f"file_json_config_invalid_json: {exc.msg}",
                error_code="CONFIG_INVALID_JSON",
            )
        result = _validate_runtime_config_payload(
            payload=payload,
            error_prefix="file_json_config",
        )
        if not result.is_success:
            return result
        return OperationResult.success(
            data=result.data,
            message=(
                f"file_json_config_loaded path={path} "
                f"policies={len(result.data.policies) if result.data else 0}"
            ),
        )


# ---------------------------------------------------------------------------
# Loader Factory
# ---------------------------------------------------------------------------
def get_access_sync_config_loader(source: str) -> AccessSyncConfigLoader:
    """Return the config loader for the given source string.

    Args:
        source: One of 'bundle', 'inline_json', 'file_json', 'dynamodb', 's3', 'ssm'.

    Returns:
        An AccessSyncConfigLoader instance.

    Raises:
        NotImplementedError: For sources that are not yet implemented.
    """
    if source == "bundle":
        return BundleConfigLoader()

    if source == "inline_json":
        return InlineJsonConfigLoader()

    if source == "file_json":
        return FileJsonConfigLoader()

    raise NotImplementedError(
        f"Access Sync config source '{source}' is not yet implemented. "
        "Use ACCESS_SYNC_CONFIG_SOURCE=bundle, inline_json, or file_json for local development."
    )
