# Access Sync

Synchronizes user access between the Identity Provider (IDP) and external platforms (AWS Identity Center, etc.) based on IDP security group membership.

---

## How it works

1. **Config loads** at startup from the source selected by `ACCESS_CONFIG_SOURCE`. It defines the organization-wide group naming convention (`dir_prefix`, `dir_separator`) and one `PlatformPolicy` per platform.
2. **Group slugs are derived** from the config — not stored. For a platform `aws` with `dir_prefix=sg` and `dir_separator=-`, the prefix is `sg-aws-` and the authn group slug is `sg-aws-authn`.
3. **Desired state is built** by querying the IDP for group membership under that prefix. Each IDP group `sg-aws-{token}` maps to `entitlement_id={token}`.
4. **Current state is fetched** from the platform via its adapter.
5. **`PolicyEngine` plans** the delta — provision (when absent), add/remove entitlements, disable/remove — as a pure, side-effect-free operation.
6. **The adapter executes** the planned actions against the platform API.
7. **Results are persisted** via `SyncRunRepository` and domain events are emitted.

Two entry points:
- `sync_user(user_email, platform)` — on-demand, single-user convergence (e.g. triggered by a Slack command)
- `sync_platform(platform)` — scheduled batch reconciliation of all users

---

## Configuration

Runtime config is a JSON document with this shape:

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

| Field | Description |
|---|---|
| `dir_prefix` | Organization-wide IDP group prefix (e.g. `sg`) |
| `dir_separator` | Separator between prefix segments (almost always `-`) |
| `platforms.<key>` | Platform key, used to look up adapters and derive slugs |
| `authn_token` | Token segment for the lifecycle group (default: `authn`) |
| `authn_removal_mode` | Action when a user leaves the authn group: `delete`, `disable`, or `entitlement_only` |

### Config sources (set via env vars)

Env var `ACCESS_CONFIG_SOURCE` controls which loader is used. It is read from `settings.config.source` in `AccessSettings` (defined in `packages/access/common/settings.py`).

| `ACCESS_CONFIG_SOURCE` | `ACCESS_CONFIG_REF` | When to use |
|---|---|---|
| `bundle` (default) | ignored | Local dev — no platforms configured, feature in waiting mode |
| `file_json` | Absolute path to a local JSON file | Local dev with a real config (e.g. `access-sync.local.json`) |
| `inline_json` | The full JSON document as a string | Useful in CI or one-off testing |
| `env` | ignored | **Production via SSM bundle** — reads flat env vars (see below) |
| `dynamodb` / `s3` / `ssm` | Key/path in that store | Not yet implemented |

### env source (production)

When `ACCESS_CONFIG_SOURCE=env`, no JSON file or inline document is needed. The loader reads three env vars that `entry.sh` populates from the SSM parameter bundle at container startup:

```
ACCESS_CONFIG_SOURCE=env
ACCESS_SYNC_DIR_PREFIX=sg
ACCESS_SYNC_DIR_SEPARATOR=-
ACCESS_SYNC_PLATFORMS_JSON={"aws": {"authn_token": "authn", "authn_removal_mode": "delete"}}
```

`ACCESS_SYNC_PLATFORMS_JSON` is the platforms block only — not the full config document. Add these vars to the `sre-bot-config` (or `sre-bot-config-infrastructure`) SSM parameter alongside the other app config.

**For local development**, use `file_json` instead:

```
ACCESS_CONFIG_SOURCE=file_json
ACCESS_CONFIG_REF=/workspace/app/packages/access/access.local.json
```

### Operational settings

All sync operational settings are in `AccessSyncSettings` (a slice of `AccessSettings` in `packages/access/common/settings.py`):

| Env var | Default | Description |
|---|---|---|
| `ACCESS_SYNC_ENABLED` | `false` | Master on/off switch |
| `ACCESS_SYNC_RECONCILIATION_ENABLED` | `false` | Enable scheduled batch sync |
| `ACCESS_SYNC_RECONCILIATION_SCHEDULE` | `03:00` | Daily run time (UTC, HH:MM) |
| `ACCESS_SYNC_JOB_TTL_SECONDS` | `86400` | Retention for completed/failed job records |
| `ACCESS_SYNC_LOCK_STALE_SECONDS` | `14400` | Running lock older than this is treated as stale |

### Scheduled reconciliation

```
ACCESS_SYNC_ENABLED=true
ACCESS_SYNC_RECONCILIATION_ENABLED=true
ACCESS_SYNC_RECONCILIATION_SCHEDULE=03:00   # UTC, HH:MM
```

---

## Adding a new platform adapter

1. **Create the adapter class** in `adapters/<platform>.py`. Implement the `AccessSyncAdapter` protocol:

   ```python
     class MyPlatformAdapter:
       def capabilities(self) -> AdapterCapabilities: ...
       def ensure_user(self, user_email: str) -> OperationResult: ...
       def disable_user(self, user_email: str) -> OperationResult: ...
       def remove_user(self, user_email: str) -> OperationResult: ...
       def apply_entitlement(self, user_email: str, entitlement_type: str, entitlement_id: str) -> OperationResult: ...
       def remove_entitlement(self, user_email: str, entitlement_type: str, entitlement_id: str) -> OperationResult: ...
       def get_current_entitlement_ids(self, user_email: str) -> OperationResult: ...
       def list_all_provisioned_users(self) -> OperationResult: ...
       def list_group_members(self, group_id: str) -> OperationResult: ...
   ```

   Rules:
   - All methods must be **idempotent** — calling twice with the same inputs must have the same effect.
   - Do **not** implement policy logic — whether to add or remove is decided by `PolicyEngine`, not the adapter.
   - Wrap all external API calls in `try/except` and return `OperationResult` — never raise across this boundary.
   - Obtain platform clients from `infrastructure.services`, not by instantiating them directly.

2. **Register the adapter** in `providers.py` inside `get_access_sync_adapters()`:

   ```python
   if platform_key == "myplatform":
       adapters[platform_key] = MyPlatformAdapter(...)
   ```

3. **Add the platform to config** — add `"myplatform": { "authn_token": "authn", "authn_removal_mode": "delete" }` to the `platforms` block in your config document.

4. **Write tests** — unit tests go in `tests/unit/packages/access/sync/`. Use the `FakePlatformAdapter` as a reference for a minimal correct implementation.

---

## Module map

| File | Purpose |
|---|---|
| `policies.py` | Business rules, data models, `PolicyEngine`. **Read this first.** |
| `config/__init__.py` | Re-exports `AccessRuntimeConfig` for backwards compatibility |
| `config/loaders.py` | Config loader implementations and JSON input validation |
| `adapters/__init__.py` | `AccessSyncAdapter` protocol and capability models |
| `adapters/aws_identity_center.py` | AWS Identity Center adapter (reference implementation) |
| `adapters/fake_platform.py` | In-memory fake adapter for tests and local dev |
| `coordinator.py` | Orchestration — wires policy, desired state, adapter, and persistence |
| `desired_state.py` | IDP directory queries → `DesiredUserState` |
| `domain.py` | Pure domain types (`SyncOutcome`, `ReconciliationOutcome`, etc.) |
| `providers.py` | `@lru_cache` singletons — the only place the object graph is assembled |
| `store.py` | `SyncRunRepository` — persists audit records |
| `transport/` | HTTP routes and Slack command handlers |

**Settings** live in `packages/access/common/settings.py` as `AccessSyncSettings` (slice of `AccessSettings`).
