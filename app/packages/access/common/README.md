# Access Common

Shared contracts for the access domain. Contains only types, constants, and helpers. No business logic, no hookimpl registrations.

---

## Contents

### `settings.py` — `AccessSettings`

The single unified settings object for the entire access feature. Loaded once from the environment; all sub-features read their slice from it.

```python
from packages.access.common.settings import get_access_settings

settings = get_access_settings()
settings.config.source          # ACCESS_CONFIG_SOURCE
settings.sync.enabled           # ACCESS_SYNC_ENABLED
settings.requests.enabled       # ACCESS_REQUESTS_ENABLED
settings.catalog.enabled        # ACCESS_CATALOG_ENABLED
```

**Env var → Python attribute mapping:**

| Env var | Python attribute | Default |
|---|---|---|
| `ACCESS_CONFIG_SOURCE` | `settings.config.source` | `bundle` |
| `ACCESS_CONFIG_REF` | `settings.config.ref` | `default` |
| `ACCESS_CONFIG_REFRESH_SECONDS` | `settings.config.refresh_seconds` | `300` |
| `ACCESS_SYNC_ENABLED` | `settings.sync.enabled` | `false` |
| `ACCESS_SYNC_RECONCILIATION_ENABLED` | `settings.sync.reconciliation_enabled` | `false` |
| `ACCESS_SYNC_RECONCILIATION_SCHEDULE` | `settings.sync.reconciliation_schedule` | `03:00` |
| `ACCESS_SYNC_JOB_TTL_SECONDS` | `settings.sync.job_ttl_seconds` | `86400` |
| `ACCESS_SYNC_LOCK_STALE_SECONDS` | `settings.sync.lock_stale_seconds` | `14400` |
| `ACCESS_REQUESTS_ENABLED` | `settings.requests.enabled` | `false` |
| `ACCESS_REQUESTS_MANAGER_GROUP_SLUG` | `settings.requests.manager_group_slug` | `sg-managers` |
| `ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG` | `settings.requests.fallback_approver_slug` | `sg-org-admins` |
| `ACCESS_REQUESTS_MIN_APPROVER_COUNT` | `settings.requests.min_approver_count` | `1` |
| `ACCESS_REQUESTS_REQUEST_TTL_HOURS` | `settings.requests.request_ttl_hours` | `72` |
| `ACCESS_CATALOG_ENABLED` | `settings.catalog.enabled` | `false` |

Each sub-feature slice may also be set via a **single JSON env var** instead of individual flat vars:

```bash
ACCESS_SYNC='{"enabled": true, "job_ttl_seconds": 3600}'
ACCESS_REQUESTS='{"enabled": true, "min_approver_count": 2}'
```

Adding a new sub-feature: add a `BaseModel` subclass and a field to `AccessSettings` in `settings.py`. No new `BaseSettings` subclass or provider needed.

### `config/settings.py` — `AccessRuntimeConfig`

The shared runtime config model, loaded from an external document (JSON file, DynamoDB row, etc.) — **not** from env vars. Constructed once at startup via `get_access_runtime_config()` in `providers.py`.

Key fields:

| Field | Example | Description |
|---|---|---|
| `dir_prefix` | `sg` | Org-wide IDP group prefix |
| `dir_separator` | `-` | Segment separator |
| `platforms` | `{"aws": PlatformPolicy(...)}` | Per-platform policy |

Key methods:

| Method | Returns | Example |
|---|---|---|
| `group_prefix(platform)` | `str` | `"sg-aws-"` |
| `authn_group_slug(platform)` | `str` | `"sg-aws-authn"` |

### `config/loaders.py`

Config loader implementations. The source is selected by `ACCESS_CONFIG_SOURCE` (via `settings.config.source`). Supported sources: `bundle`, `file_json`, `inline_json`, `env`.

### `events.py`

Cross-package event name constants.

| Constant | Value | Direction |
|---|---|---|
| `REQUEST_APPROVED` | `access_request_approved` | `request` → `sync` |

### `naming.py` — `AccessGroupNaming`

Derives canonical IDP group slugs from config.

```python
naming = AccessGroupNaming(dir_prefix="sg", dir_separator="-")
naming.group_prefix("aws")           # "sg-aws-"
naming.authn_group_slug("aws")       # "sg-aws-authn"
```

### `providers.py`

| Provider | Returns | Description |
|---|---|---|
| `get_access_settings()` | `AccessSettings` | Singleton — unified feature settings (cached) |
| `get_access_runtime_config()` | `AccessRuntimeConfig` | Singleton — runtime config document (cached) |

---

## Conventions

- No imports from `request/`, `sync/`, or `catalog/` — dependency direction is always inward.
- No hookimpl functions — this is not a feature plugin.
- All runtime config models are frozen dataclasses. Settings sub-models are plain `BaseModel`.
