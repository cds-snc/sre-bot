# Access Common

Shared contracts for the access domain. Contains only types, constants, and helpers. No business logic, no hookimpl registrations.

---

## Contents

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

### `config/settings.py` — `AccessRuntimeConfig`
The single shared runtime config model. Constructed once at startup, injected into both `request` and `sync` packages.

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
Config loader implementations. Reads from `file_json`, `inline_json`, `env`, `bundle` sources controlled by `ACCESS_CONFIG_SOURCE`.

---

## Conventions

- No imports from `request/` or `sync/` — dependency direction is always inward.
- No hookimpl functions — this is not a feature plugin.
- All models are frozen dataclasses.
