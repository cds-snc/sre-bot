"""Access Sync config loaders.

Loader contract (AccessSyncConfigLoader protocol), all built-in loader
implementations, JSON input models, shared validation helpers, and the
loader factory.

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
from pathlib import Path
from typing import Dict, List, Optional, Protocol

from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.config.settings import AccessSyncRuntimeConfig
from packages.access_sync.policies import (
    DefaultEntitlementStrategy,
    EntitlementMode,
    EntitlementStrategyKind,
    EntitlementRule,
    PatternEntitlementMapping,
    PlatformPolicy,
)


# ---------------------------------------------------------------------------
# Key Normalization
# ---------------------------------------------------------------------------
def normalize_target_key(value: str) -> str:
    """Return the canonical form of a target-system key.

    All policy and adapter maps must use this normalized value as their key so
    that lookups behave consistently regardless of input casing or whitespace.
    """
    return value.strip().lower()


# ---------------------------------------------------------------------------
# Runtime Config Input Models (JSON)
# ---------------------------------------------------------------------------
class EntitlementRuleConfigModel(BaseModel):
    """Typed schema for one entitlement rule in runtime config JSON."""

    group_slug: str
    entitlement_type: str
    entitlement_id: str
    mode: EntitlementMode = "sync_managed"


class PatternEntitlementMappingConfigModel(BaseModel):
    """Typed schema for one wildcard group->entitlement mapping."""

    source_group_pattern: str
    entitlement_type: str
    entitlement_id: str
    mode: EntitlementMode = "sync_managed"


class DefaultEntitlementStrategyConfigModel(BaseModel):
    """Typed schema for platform-level default entitlement strategy."""

    kind: EntitlementStrategyKind = "explicit_rules_only"
    source_group_prefix: str = ""
    exclude_group_slugs: List[str] = Field(default_factory=list)
    default_entitlement_type: str = "group"
    entitlement_id_template: str = "{token}"
    mode: EntitlementMode = "sync_managed"
    pattern_mappings: List[PatternEntitlementMappingConfigModel] = Field(
        default_factory=list
    )


class PlatformPolicyConfigModel(BaseModel):
    """Typed schema for one platform policy in runtime config JSON."""

    platform: str
    authn_group_slug: str
    authn_mode: str
    authn_removal_mode: str
    entitlement_rules: List[EntitlementRuleConfigModel] = Field(default_factory=list)
    default_entitlement_strategy: Optional[DefaultEntitlementStrategyConfigModel] = None


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
            default_entitlement_strategy=(
                DefaultEntitlementStrategy(
                    kind=raw_policy.default_entitlement_strategy.kind,
                    source_group_prefix=(
                        raw_policy.default_entitlement_strategy.source_group_prefix
                    ),
                    exclude_group_slugs=list(
                        raw_policy.default_entitlement_strategy.exclude_group_slugs
                    ),
                    default_entitlement_type=(
                        raw_policy.default_entitlement_strategy.default_entitlement_type
                    ),
                    entitlement_id_template=(
                        raw_policy.default_entitlement_strategy.entitlement_id_template
                    ),
                    mode=raw_policy.default_entitlement_strategy.mode,
                    pattern_mappings=[
                        PatternEntitlementMapping(
                            source_group_pattern=mapping.source_group_pattern,
                            entitlement_type=mapping.entitlement_type,
                            entitlement_id=mapping.entitlement_id,
                            mode=mapping.mode,
                        )
                        for mapping in raw_policy.default_entitlement_strategy.pattern_mappings
                    ],
                )
                if raw_policy.default_entitlement_strategy is not None
                else None
            ),
        )
        policies[normalize_target_key(str(policy.platform or fallback_key))] = policy

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
