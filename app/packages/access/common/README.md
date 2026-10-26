# Access Common

Shared contracts for the access domain. Contains only types, constants, and helpers. No business logic, no hookimpl registrations.

---

## Contents

### `settings.py` — one settings class per access plugin

Each class reads only its own `ACCESS_<SUB>_` names and is built by the provider of the plugin that needs it, so a disabled plugin never validates its settings. Whether a plugin runs is its `[plugins.platform_access]` key, not a setting here.

| Class | Env prefix | Built by |
|---|---|---|
| `AccessConfigSettings` | `ACCESS_CONFIG_` | `get_access_config_settings()` in `common/providers.py` (every access plugin) |
| `AccessSyncSettings` | `ACCESS_SYNC_` | `get_access_sync_settings()` in `sync/providers.py` |
| `AccessRequestsSettings` | `ACCESS_REQUESTS_` | `get_access_request_settings()` in `request/providers.py` |

`AccessRequestsSettings` requires `ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG`; it is built only when `access.request` is enabled. A new access plugin with settings adds its own class with its own prefix.

### `config/settings.py` — `AccessRuntimeConfig`

The shared runtime config model, loaded from an external document (JSON file, DynamoDB row, etc.) — **not** from env vars. Constructed once at startup via `get_access_runtime_config()` in `providers.py`.

Key fields:

| Field | Example | Description |
|---|---|---|
| `dir_prefix` | `sg` | Org-wide IDP group prefix |
| `dir_domain` | `cds-snc.ca` | Email domain of managed IDP groups; required, no default |
| `dir_separator` | `-` | Segment separator |
| `platforms` | `{"aws": PlatformPolicy(...)}` | Per-platform policy |

Key methods:

| Method | Returns | Example |
|---|---|---|
| `group_prefix(platform)` | `str` | `"sg-aws-"` |
| `authn_group_slug(platform)` | `str` | `"sg-aws-authn"` |

### `config/loaders.py`

Config loader implementations. The source is selected by `ACCESS_CONFIG_SOURCE` (via `settings.config.source`). Supported sources: `bundle`, `file_json`, `inline_json`, `env`. The default `bundle` source carries no configuration and reports `CONFIG_NOT_CONFIGURED`.

### `events.py`

Cross-package event name constants.

| Constant | Value | Direction |
|---|---|---|
| `REQUEST_APPROVED` | `access_request_approved` | `request` → `sync` |

### `naming.py` — `AccessGroupNaming`

Derives canonical IDP group slugs from config.

```python
naming = AccessGroupNaming(dir_prefix="sg", dir_separator="-")
naming.group_prefix("aws")  # "sg-aws-"
naming.authn_group_slug("aws")  # "sg-aws-authn"
```

### `providers.py`

| Provider | Returns | Description |
|---|---|---|
| `get_access_config_settings()` | `AccessConfigSettings` | Singleton — runtime config source and ref (cached) |
| `get_access_runtime_config()` | `AccessRuntimeConfig` | Singleton — runtime config document (cached) |

---

## Conventions

- No imports from `request/`, `sync/`, or `catalog/` — dependency direction is always inward.
- No hookimpl functions — this is not a feature plugin.
- All runtime config models are frozen dataclasses. Settings sub-models are plain `BaseModel`.
