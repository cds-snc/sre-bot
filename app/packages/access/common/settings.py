"""Unified access feature settings — one load, tree-shaped access.

The entire access feature is configured through a single ``AccessSettings``
root object.  Sub-features (sync, requests, catalog) each have their own
slice, accessed as attributes:

    settings = get_access_settings()
    settings.sync.enabled          # ACCESS_SYNC_ENABLED
    settings.requests.enabled      # ACCESS_REQUESTS_ENABLED
    settings.catalog.enabled       # ACCESS_CATALOG_ENABLED
    settings.config.source         # ACCESS_CONFIG_SOURCE

Adding a new sub-feature requires only:
1. A new ``BaseModel`` subclass in this file.
2. A new field on ``AccessSettings``.
3. Env vars following the ``ACCESS_{SUBFEATURE}_{FIELD}`` convention.
No new ``BaseSettings`` subclass is needed.

``AccessRuntimeConfig`` is a separate concept — it is a structured document
loaded at runtime from an external source (bundle, DynamoDB, etc.) and is
not part of this env-var settings consolidation.
"""

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AccessConfigSettings(BaseModel):
    """Bootstrap: how to locate the AccessRuntimeConfig document.

    Env vars:
        ACCESS_CONFIG_SOURCE  — loader backend (bundle | inline_json | file_json | env)
        ACCESS_CONFIG_REF     — reference key passed to the loader (table row PK, S3 key, etc.)
        ACCESS_CONFIG_REFRESH_SECONDS — reserved for future cache invalidation
    """

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


class AccessSyncSettings(BaseModel):
    """Operational settings for the Access Sync sub-feature.

    Env vars:
        ACCESS_SYNC_ENABLED                  — master on/off switch
        ACCESS_SYNC_RECONCILIATION_ENABLED   — enable scheduled full-platform sync
        ACCESS_SYNC_RECONCILIATION_SCHEDULE  — daily sync run time HH:MM (UTC)
        ACCESS_SYNC_JOB_TTL_SECONDS          — retention for completed/failed job records
        ACCESS_SYNC_LOCK_STALE_SECONDS       — running lock older than this is considered stale
    """

    enabled: bool = False
    reconciliation_enabled: bool = False
    reconciliation_schedule: str = "03:00"
    job_ttl_seconds: int = 86400
    lock_stale_seconds: int = 14400


class AccessRequestsSettings(BaseModel):
    """Operational settings for the Access Requests sub-feature.

    Env vars:
        ACCESS_REQUESTS_ENABLED                 — master on/off switch
        ACCESS_REQUESTS_MANAGER_GROUP_SLUG      — IDP group whose members may submit delegated requests
        ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG  — org-level approver fallback group slug
        ACCESS_REQUESTS_MIN_APPROVER_COUNT      — minimum affirmative decisions to approve
        ACCESS_REQUESTS_REQUEST_TTL_HOURS       — hours before a pending request expires
    """

    enabled: bool = False
    manager_group_slug: str = "sg-managers"
    fallback_approver_slug: str = "sg-org-admins"
    min_approver_count: int = 1
    request_ttl_hours: int = 72


class AccessCatalogSettings(BaseModel):
    """Operational settings for the Access Catalog sub-feature.

    Env vars:
        ACCESS_CATALOG_ENABLED — master on/off switch
    """

    enabled: bool = False


class AccessSettings(BaseSettings):
    """Unified access feature settings — one load for the entire feature.

    Uses ``env_prefix="ACCESS_"``, ``env_nested_delimiter="_"``, and
    ``env_nested_max_split=1`` so that existing env var names are preserved
    with no SSM parameter renames:

        ACCESS_SYNC_ENABLED              → settings.sync.enabled
        ACCESS_SYNC_JOB_TTL_SECONDS      → settings.sync.job_ttl_seconds
        ACCESS_REQUESTS_ENABLED          → settings.requests.enabled
        ACCESS_CATALOG_ENABLED           → settings.catalog.enabled
        ACCESS_CONFIG_SOURCE             → settings.config.source

    ``case_sensitive=False`` is required: pydantic-settings uses field names
    (lowercase) to build the env key prefix when matching nested models, so
    case-insensitive lookup is needed to match uppercase OS env vars.
    """

    model_config = SettingsConfigDict(
        env_prefix="ACCESS_",
        env_nested_delimiter="_",
        env_nested_max_split=1,
        case_sensitive=False,
        extra="ignore",
        env_file=".env",
    )

    config: AccessConfigSettings = Field(default_factory=AccessConfigSettings)
    sync: AccessSyncSettings = Field(default_factory=AccessSyncSettings)
    requests: AccessRequestsSettings = Field(default_factory=AccessRequestsSettings)
    catalog: AccessCatalogSettings = Field(default_factory=AccessCatalogSettings)


@lru_cache(maxsize=1)
def get_access_settings() -> AccessSettings:
    """Return the singleton AccessSettings instance.

    One env read for the entire access feature.  Cached for the process lifetime.
    """
    return AccessSettings()
