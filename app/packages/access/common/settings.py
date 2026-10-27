"""Access feature settings — one settings class per access plugin.

Each class reads only its own ``ACCESS_<SUB>_`` environment names and is built
by the provider of the plugin that needs it, so a disabled plugin never
validates its settings (decisions/configuration.md):

    AccessConfigSettings    ACCESS_CONFIG_*    common/providers.py (every access plugin)
    AccessSyncSettings      ACCESS_SYNC_*      sync/providers.py
    AccessRequestsSettings  ACCESS_REQUESTS_*  request/providers.py

and one slice on the configuration files, read at use (a disabled plugin never builds it):

    AccessPermissionSetsSettings  [access_permission_sets]  get_access_permission_sets_settings()

Whether a plugin runs is its ``[plugins.platform_access]`` key, not a setting
here. ``AccessRuntimeConfig`` is a separate concept: a structured document
loaded at runtime from the source these settings name.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class AccessConfigSettings(BaseSettings):
    """Bootstrap: how to locate the AccessRuntimeConfig document.

    Env vars:
        ACCESS_CONFIG_SOURCE  — loader backend (bundle | inline_json | file_json | env)
        ACCESS_CONFIG_REF     — reference key passed to the loader (table row PK, S3 key, etc.)
        ACCESS_CONFIG_REFRESH_SECONDS — reserved for future cache invalidation
    """

    model_config = SettingsConfigDict(env_prefix="ACCESS_CONFIG_", case_sensitive=False, extra="ignore", env_file=".env")

    source: Literal["bundle", "inline_json", "file_json", "env"] = "bundle"
    ref: str = "default"
    refresh_seconds: int = 300

    @field_validator("source", mode="before")
    @classmethod
    def _validate_source(cls, value: object) -> object:
        allowed = {"bundle", "inline_json", "file_json", "env"}
        if isinstance(value, str) and value not in allowed:
            raise ValueError("ACCESS_CONFIG_SOURCE must be one of: bundle, inline_json, file_json, env")
        return value


class AccessSyncSettings(BaseSettings):
    """Operational settings for the access.sync plugin.

    Env vars:
        ACCESS_SYNC_RECONCILIATION_ENABLED   — enable scheduled full-platform sync
        ACCESS_SYNC_RECONCILIATION_SCHEDULE  — daily sync run time HH:MM (UTC)
        ACCESS_SYNC_JOB_TTL_SECONDS          — retention for completed/failed job records
        ACCESS_SYNC_LOCK_STALE_SECONDS       — running lock older than this is considered stale
        ACCESS_SYNC_TABLE_NAME               — record table holding sync runs
        ACCESS_SYNC_JOB_STATUS_TABLE_NAME    — record table holding job and lock-holder status
                                               (shared with the idempotency store)
    """

    model_config = SettingsConfigDict(env_prefix="ACCESS_SYNC_", case_sensitive=False, extra="ignore", env_file=".env")

    reconciliation_enabled: bool = False
    reconciliation_schedule: str = "03:00"
    job_ttl_seconds: int = 86400
    lock_stale_seconds: int = 14400
    table_name: str = "sre_bot_access"
    job_status_table_name: str = "sre_bot_idempotency"


class AccessRequestsSettings(BaseSettings):
    """Operational settings for the access.request plugin.

    Env vars:
        ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG  — org-level approver fallback group slug;
                                                  required, no default
        ACCESS_REQUESTS_MIN_APPROVER_COUNT      — minimum affirmative decisions to approve
        ACCESS_REQUESTS_REQUEST_TTL_HOURS       — hours before a pending request expires
        ACCESS_REQUESTS_TABLE_NAME              — record table holding requests, decisions and audit entries
    """

    model_config = SettingsConfigDict(env_prefix="ACCESS_REQUESTS_", case_sensitive=False, extra="ignore", env_file=".env")

    fallback_approver_slug: str = ""
    min_approver_count: int = 1
    request_ttl_hours: int = 72
    table_name: str = "sre_bot_access_requests"

    @model_validator(mode="after")
    def _validate_fallback_approver_slug(self) -> AccessRequestsSettings:
        # Built only by the access.request provider, so the requirement holds exactly when that plugin is enabled.
        if not self.fallback_approver_slug.strip():
            raise ValueError("ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG must be set when the access.request plugin is enabled")
        return self


class AccessPermissionSetsSettings(ConfigurationSlice):
    """The AWS SSO permission sets the "write" and "read" access aliases resolve to.

    Keys of [access_permission_sets]:
        system_admin_permissions — permission set ARN the "write" alias resolves to
        view_only_permissions    — permission set ARN the "read" alias resolves to

    Both are public values, empty until an environment file names them; the permission-set
    policy itself is redesigned in the access feature.
    """

    model_config = SettingsConfigDict(toml_table_header=("access_permission_sets",), env_prefix="ACCESS_PERMISSION_SETS__")

    system_admin_permissions: str = ""
    view_only_permissions: str = ""


@lru_cache(maxsize=1)
def get_access_permission_sets_settings() -> AccessPermissionSetsSettings:
    """Return the process-wide `AccessPermissionSetsSettings` singleton."""
    return AccessPermissionSetsSettings()
