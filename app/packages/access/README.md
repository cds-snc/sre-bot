# Access Domain

The `access` package contains all business logic for managing user access to external platforms. It is split into focused sub-packages that share a common config model and event contract.

---

## Sub-packages

| Package | Purpose |
|---|---|
| `common/` | Shared config models, naming helpers, and event constants — no business logic |
| `request/` | Access request lifecycle: submission, approval, rejection, retry |
| `sync/` | IDP-to-platform synchronization: on-demand and scheduled reconciliation |
| `catalog/` | Read-only entitlement catalog for browsing available groups |

---

## Feature settings

All access feature settings are unified under a single `AccessSettings` object (defined in `packages/access/common/settings.py`, loaded once via `get_access_settings()`).

| Env var | Default | Description |
|---|---|---|
| `ACCESS_CONFIG_SOURCE` | `bundle` | Runtime config source: `bundle`, `file_json`, `inline_json`, `env` |
| `ACCESS_CONFIG_REF` | `default` | Path or key for the config source |
| `ACCESS_CONFIG_REFRESH_SECONDS` | `300` | How often to re-read a dynamic config source |
| `ACCESS_SYNC_ENABLED` | `false` | Enable the sync feature |
| `ACCESS_SYNC_RECONCILIATION_ENABLED` | `false` | Enable scheduled batch reconciliation |
| `ACCESS_SYNC_RECONCILIATION_SCHEDULE` | `03:00` | Daily reconciliation time (UTC, HH:MM) |
| `ACCESS_SYNC_JOB_TTL_SECONDS` | `86400` | Retention for completed/failed sync records |
| `ACCESS_SYNC_LOCK_STALE_SECONDS` | `14400` | Lock age before a running job is treated as stale |
| `ACCESS_REQUESTS_ENABLED` | `false` | Enable the access requests feature |
| `ACCESS_REQUESTS_MANAGER_GROUP_SLUG` | `sg-managers` | Primary approver group |
| `ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG` | `sg-org-admins` | Fallback approver group |
| `ACCESS_REQUESTS_MIN_APPROVER_COUNT` | `1` | Approvals needed before a request is approved |
| `ACCESS_REQUESTS_REQUEST_TTL_HOURS` | `72` | Hours before an open request expires |
| `ACCESS_CATALOG_ENABLED` | `false` | Enable the catalog browse feature |

Sub-feature settings may also be set via a single JSON env var:

```bash
ACCESS_SYNC='{"enabled": true, "job_ttl_seconds": 3600}'
ACCESS_REQUESTS='{"enabled": true, "min_approver_count": 2}'
```

---

## Shared runtime config

All sub-packages share a single `AccessRuntimeConfig` instance loaded once at startup. It defines the IDP group naming convention and per-platform policy.

```json
{
  "dir_prefix": "sg",
  "dir_separator": "-",
  "platforms": {
    "aws": {
      "authn_token": "authn",
      "authn_removal_mode": "delete"
    }
  }
}
```

**Local dev config file**: `packages/access/access.local.json`

Point to it with:
```
ACCESS_CONFIG_SOURCE=file_json
ACCESS_CONFIG_REF=/workspace/app/packages/access/access.local.json
```

---

## How the sub-packages interact

```
User submits request
        │
        ▼
  [access/request]
  - Validates group exists in IDP
  - Derives entitlement token from group slug
  - Writes member to IDP (source of truth)
  - Emits access_request_approved event
        │
        ▼
  [access/sync]  ← listens for access_request_approved
  - Reads desired state from IDP membership
  - Reconciles against platform (AWS Identity Center, etc.)
  - Emits sync_completed / sync_failed
        │
        ▼
  [access/request]  ← listens for sync_completed / sync_failed
  - Transitions request to completed or failed
```

The IDP (Google Workspace) is always the source of truth for group membership. Access Sync reads from it, never writes to it.

---

## How to write platform policies

The runtime config JSON is the single place you define the group naming convention and per-platform behaviour. All sub-packages read from this one document.

### Minimal config

```json
{
  "dir_prefix": "sg",
  "dir_separator": "-",
  "platforms": {
    "aws": {
      "authn_token": "authn",
      "authn_removal_mode": "delete"
    }
  }
}
```

| Field | Type | Description |
|---|---|---|
| `dir_prefix` | string | Leading segment of every managed IDP group slug (e.g. `sg`) |
| `dir_separator` | string | Separator between naming segments (almost always `-`) |
| `platforms` | object | One key per active platform; key is the `platform` value used in API calls |

### Per-platform fields (`PlatformPolicy`)

| Field | Type | Default | Description |
|---|---|---|---|
| `authn_token` | string | `"authn"` | Token segment that identifies the authentication group. The full slug is `{dir_prefix}{sep}{platform}{sep}{authn_token}` — e.g. `sg-aws-authn` |
| `authn_removal_mode` | string | `"delete"` | What Access Sync does when a user loses authn group membership: `delete` removes the platform user, `disable` deactivates them, `entitlement_only` removes entitlements but leaves the account |
| `mode_overrides` | object | `{}` | Per-entitlement-token overrides — see below |

### Entitlement mode overrides

By default every managed group is `sync_managed` — Access Sync will enforce its membership state. Use `mode_overrides` when you need to carve out exceptions:

```json
{
  "dir_prefix": "sg",
  "dir_separator": "-",
  "platforms": {
    "aws": {
      "authn_token": "authn",
      "authn_removal_mode": "delete",
      "mode_overrides": {
        "scratch": "ephemeral",
        "root-admin": "deactivated"
      }
    }
  }
}
```

| Mode | Effect on Access Sync | Effect on Access Requests |
|---|---|---|
| `sync_managed` | _(default)_ Group is reconciled every sync run | Requests accepted; `requestable=true` in catalog |
| `ephemeral` | Group is excluded from reconciliation (no state enforcement) | Requests rejected (`ENTITLEMENT_MODE_EPHEMERAL`); use the elevated-access workflow instead |
| `deactivated` | Group is excluded from reconciliation | Requests rejected (`ENTITLEMENT_MODE_DEACTIVATED`); contact an administrator |

The key in `mode_overrides` is the **entitlement token** — the segment after the platform prefix is stripped. For `sg-aws-scratch` with prefix `sg-aws-`, the token is `scratch`.

### Adding a new platform

1. Create the IDP groups following the naming convention: `{dir_prefix}{sep}{platform}{sep}{token}` for entitlements and `{dir_prefix}{sep}{platform}{sep}{authn_token}` for the authn group.
2. Add the entry to your runtime config JSON under `platforms`.
3. Register a platform adapter in `packages/access/sync/` (see [sync/README.md](sync/README.md)).
4. Optionally register a catalog token parser in `packages/access/catalog/providers.py`.

### Testing locally

Use `ACCESS_CONFIG_SOURCE=file_json` and point `ACCESS_CONFIG_REF` at a local file:

```json
{
  "dir_prefix": "sg",
  "dir_separator": "-",
  "platforms": {
    "aws": {
      "authn_token": "authn",
      "authn_removal_mode": "delete",
      "mode_overrides": {
        "scratch": "sync_managed"
      }
    },
    "fake": {
      "authn_token": "authn",
      "authn_removal_mode": "delete"
    }
  }
}
```

The `fake` platform is served by `FakePlatformAdapter` and makes zero external API calls — useful for validating the sync pipeline without AWS credentials.

