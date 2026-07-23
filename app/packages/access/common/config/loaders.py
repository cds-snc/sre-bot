"""Access domain config loaders.

Loader contract and all built-in loader implementations for loading
AccessRuntimeConfig.  This module serves the entire access feature domain —
sync, catalog, and request all share one runtime config loaded here.

Config loader sources:
    bundle      - Built-in empty bundle. Default for local development.
    inline_json - Parse ACCESS_CONFIG_REF as inline JSON text.
    file_json   - Read ACCESS_CONFIG_REF as a path to a local JSON file.
    env         - Read from ACCESS_CONFIG_ENV_DIR_PREFIX / ACCESS_CONFIG_ENV_PLATFORMS_JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.config.settings import (
    AccessRuntimeConfig,
    CatalogExtensions,
    CatalogParserConfig,
    EntitlementMode,
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
# Loader Protocol
# ---------------------------------------------------------------------------


class AccessConfigLoader(Protocol):
    """Protocol for loading access runtime configuration."""

    def load(self, ref: str) -> OperationResult[AccessRuntimeConfig]:
        """Load access runtime configuration by source-specific reference."""
        ...


# ---------------------------------------------------------------------------
# Runtime Config Input Models (JSON)
# ---------------------------------------------------------------------------


class PlatformPolicyConfigModel(BaseModel):
    """Typed schema for one platform policy in runtime config JSON."""

    authn_token: str = "authn"  # noqa: S105 -- default group-slug token, not a credential
    authn_removal_mode: str = "delete"
    adapter_type: str = "fake"
    mode_overrides: dict[str, EntitlementMode] = Field(default_factory=dict)


class CatalogParserConfigModel(BaseModel):
    """Typed schema for one platform parser config in extensions."""

    known_envs: list[str] = Field(default_factory=list)


class CatalogExtensionsConfigModel(BaseModel):
    """Typed schema for catalog extensions block in runtime config."""

    parsers: dict[str, CatalogParserConfigModel] = Field(default_factory=dict)
    platform_display_names: dict[str, str] = Field(default_factory=dict)


class RuntimeConfigJsonModel(BaseModel):
    """Top-level schema for the access runtime config JSON document.

    Expected shape::

        {
          "dir_prefix": "sg",
          "dir_separator": "-",
          "platforms": {
            "aws": {
              "authn_token": "authn",
              "authn_removal_mode": "delete",
              "mode_overrides": {"breakglass-admin": "ephemeral"}
            }
          },
          "extensions": {
            "catalog": {
              "parsers": {
                "aws": {"known_envs": ["prod", "staging"]}
              },
              "platform_display_names": {"aws": "Amazon Web Services"}
            }
          }
        }
    """

    dir_prefix: str
    dir_separator: str = "-"
    platforms: dict[str, PlatformPolicyConfigModel] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared Conversion Helpers
# ---------------------------------------------------------------------------


def _build_runtime_config(
    dir_prefix: str,
    dir_separator: str,
    platforms_model: dict[str, PlatformPolicyConfigModel],
    extensions: dict[str, Any] | None = None,
) -> AccessRuntimeConfig:
    """Convert validated JSON platform models into ``AccessRuntimeConfig``."""
    platforms: dict[str, PlatformPolicy] = {}
    for key, raw_policy in platforms_model.items():
        platforms[normalize_target_key(key)] = PlatformPolicy(
            authn_token=raw_policy.authn_token,
            authn_removal_mode=raw_policy.authn_removal_mode,
            adapter_type=raw_policy.adapter_type,
            mode_overrides=dict(raw_policy.mode_overrides),
        )

    catalog_ext: CatalogExtensions | None = None
    if extensions and "catalog" in extensions:
        cat_model = CatalogExtensionsConfigModel.model_validate(extensions["catalog"])
        parsers = {}
        for platform_key, parser_cfg in cat_model.parsers.items():
            parsers[platform_key] = CatalogParserConfig(known_envs=list(parser_cfg.known_envs))
        catalog_ext = CatalogExtensions(
            parsers=parsers,
            platform_display_names=dict(cat_model.platform_display_names),
        )

    return AccessRuntimeConfig(
        dir_prefix=dir_prefix,
        dir_separator=dir_separator,
        platforms=platforms,
        extensions=dict(extensions or {}),
        catalog_extensions=catalog_ext,
    )


def _validate_runtime_config_payload(
    payload: object,
    error_prefix: str,
) -> OperationResult[AccessRuntimeConfig]:
    """Validate parsed JSON payload and build runtime config."""
    try:
        validated = RuntimeConfigJsonModel.model_validate(payload)
    except ValidationError as exc:
        return OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message=f"{error_prefix}_invalid_policy: {exc}",
            error_code="CONFIG_INVALID_SHAPE",
        )
    try:
        config = _build_runtime_config(
            dir_prefix=validated.dir_prefix,
            dir_separator=validated.dir_separator,
            platforms_model=validated.platforms,
            extensions=validated.extensions,
        )
    except ValidationError as exc:
        return OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message=f"{error_prefix}_invalid_extensions: {exc}",
            error_code="CONFIG_INVALID_SHAPE",
        )
    return OperationResult.success(
        data=config,
        message=f"{error_prefix}_loaded platforms={len(config.platforms)}",
    )


# ---------------------------------------------------------------------------
# Config Loaders
# ---------------------------------------------------------------------------


class BundleConfigLoader:
    """Returns an empty bundle (no platforms configured).

    The feature enters "waiting mode": no adapters are registered and
    sync_user returns POLICY_NOT_FOUND gracefully until a real source is set.
    """

    def load(self, ref: str) -> OperationResult[AccessRuntimeConfig]:
        config = AccessRuntimeConfig(dir_prefix="", platforms={})
        return OperationResult.success(
            data=config,
            message=f"bundle_config_loaded ref={ref} platforms=0 (waiting mode)",
        )


class InlineJsonConfigLoader:
    """Parses runtime policy from ACCESS_CONFIG_REF inline JSON."""

    def load(self, ref: str) -> OperationResult[AccessRuntimeConfig]:
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


class EnvConfigLoader:
    """Builds AccessRuntimeConfig from individual env vars.

    Reads:
        ACCESS_CONFIG_ENV_DIR_PREFIX     — IDP group prefix (e.g. ``sg``)
        ACCESS_CONFIG_ENV_DIR_SEPARATOR  — segment separator; default ``-``
        ACCESS_CONFIG_ENV_PLATFORMS_JSON — platforms block as a JSON string
    """

    class _EnvModel(BaseSettings):
        dir_prefix: str = Field(default="", alias="ACCESS_CONFIG_ENV_DIR_PREFIX")
        dir_separator: str = Field(default="-", alias="ACCESS_CONFIG_ENV_DIR_SEPARATOR")
        platforms_json: str = Field(default="{}", alias="ACCESS_CONFIG_ENV_PLATFORMS_JSON")

        model_config = SettingsConfigDict(
            env_file=".env",
            case_sensitive=True,
            extra="ignore",
        )

    def load(self, ref: str) -> OperationResult[AccessRuntimeConfig]:
        env = self._EnvModel()
        if not env.dir_prefix:
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message="env_config_missing_dir_prefix: ACCESS_CONFIG_ENV_DIR_PREFIX must be set",
                error_code="CONFIG_INVALID_SHAPE",
            )
        try:
            platforms_payload = json.loads(env.platforms_json)
        except json.JSONDecodeError as exc:
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message=f"env_config_invalid_platforms_json: {exc.msg}",
                error_code="CONFIG_INVALID_JSON",
            )
        return _validate_runtime_config_payload(
            payload={
                "dir_prefix": env.dir_prefix,
                "dir_separator": env.dir_separator,
                "platforms": platforms_payload,
            },
            error_prefix="env_config",
        )


class FileJsonConfigLoader:
    """Parses runtime policy from a JSON file path given in ref."""

    def load(self, ref: str) -> OperationResult[AccessRuntimeConfig]:
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
            message=(f"file_json_config_loaded path={path} platforms={len(result.data.platforms) if result.data else 0}"),
        )


# ---------------------------------------------------------------------------
# Loader Factory
# ---------------------------------------------------------------------------


def get_access_config_loader(source: str) -> AccessConfigLoader:
    """Return the config loader for the given source string.

    Args:
        source: One of 'bundle', 'inline_json', 'file_json', 'env'.

    Returns:
        An AccessConfigLoader instance.

    Raises:
        ValueError: If the source is unsupported.
    """
    if source == "bundle":
        return BundleConfigLoader()
    if source == "inline_json":
        return InlineJsonConfigLoader()
    if source == "file_json":
        return FileJsonConfigLoader()
    if source == "env":
        return EnvConfigLoader()
    raise ValueError(f"Unsupported ACCESS_CONFIG_SOURCE '{source}'. Use bundle, inline_json, file_json, or env.")
