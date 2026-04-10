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
