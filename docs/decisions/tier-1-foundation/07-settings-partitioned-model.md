# ADR-07: Partitioned Settings Model

**Date**: 2026-03-20  
**Status**: Accepted  
**Supersedes**: [`02-configuration-management.md`](02-configuration-management.md) (partially — `get_settings()` rules for routes and legacy `modules/` remain; new constraints added for `packages/`)  
**References**:
- [pydantic-settings docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [`infrastructure-core-services-cleanup.md`](../../transition/infrastructure-core-services-cleanup.md) — IS-07 tracking
- [`.github/skills/settings-singleton.md`](../../../.github/skills/settings-singleton.md) — enforcement rules

---

## Context

Configuration evolved through four phases: raw `os.getenv` → per-feature `BaseSettings` → central `Settings` aggregator → core services with pluggy. Each step was correct at the time.

The aggregator is now the problem. The plugin architecture separates `packages/` features from `infrastructure/`; forcing every new package to modify `infrastructure/configuration/settings.py` inverts that dependency. The aggregator also has no ownership boundary enforcement — `INCIDENT_CHANNEL` is already declared in both `SlackSettings` and `IncidentFeatureSettings`.

Five concrete problems:

1. Every `packages/<name>` must edit an infrastructure file to register its settings.
2. Feature settings live in `infrastructure/configuration/features/` — wrong layer, wrong owner.
3. Config key duplication exists today and will grow.
4. Services receive `Settings` when they need one section — inflated test surface.
5. `Settings.__init__` pre-instantiates every sub-settings class to work around the pydantic-settings warning that `BaseSettings`-in-`BaseSettings` causes double-initialization. This workaround grows with every new class added.

---

## Decision

Adopt a **partitioned settings model**:

### Tier 1 — Central `Settings` (transitional, not the end state)

Retained for: integration credentials (`SlackSettings`, `AwsSettings`, `GoogleWorkspaceSettings`, etc.), infrastructure behavior (`RetrySettings`, `IdempotencySettings`, `ServerSettings`, `DirectorySettings`, `PlatformsSettings`), and app-level fields (`PREFIX`, `LOG_LEVEL`, `GIT_SHA`).

Feature settings (`GroupsFeatureSettings`, `CommandsSettings`, `IncidentFeatureSettings`, `AWSFeatureSettings`, `AtipSettings`, `SreOpsSettings`) are **removed** as their `modules/` are retired or migrated.

**End state (IS-07-D + IS-07-E):** `Settings` dissolves entirely. Each integration class becomes its own independent `@lru_cache` provider. The `__init__` workaround and `settings_map` are deleted.

### Tier 2 — Feature package settings

Every `packages/<name>/` owns its settings in `packages/<name>/settings.py`. See [`settings-singleton.md`](../../../.github/skills/settings-singleton.md) for the two patterns (new package vs. migrating a legacy module).

The settings class is validated at startup via `startup_warmup` hookimpl and **never appears in `infrastructure/configuration/settings.py`**.

### Tier 3 — Services receive slices, not the full `Settings`

Providers extract the narrowest slice needed and pass it to the service constructor:

```python
# infrastructure/services/providers.py
@lru_cache(maxsize=1)
def get_aws_clients() -> AWSClients:
    settings = get_settings()
    return AWSClients(aws_settings=settings.aws)  # slice only

# infrastructure/clients/aws.py
class AWSClients:
    def __init__(self, aws_settings: AwsSettings): ...  # not Settings
```

---

## Deployment Constraints

These are sequencing constraints, not architectural ones.

### `.env` is the settings interface

All `BaseSettings` subclasses use `env_file=".env"`. `entry.sh` is the only thing that writes that file — it does not matter whether the source is SSM, Secrets Manager, or both. Adding a new source is one `>>` append line in `entry.sh`. No Python changes are needed.

### SSM constraints (tech debt)

- **Parameter size**: SSM Standard caps at 4 KB. Already split across two parameters.
- **Env var renaming**: a rolling deployment coexists old and new task definitions. Renaming a deployed key breaks the old task. Only applies to *existing* keys — new keys in a new parameter have no rename risk.
- **`get-parameters` tab-separator bug** (fixed in `entry.sh`): the plural form separates parameter values with `\t`, not `\n`, silently corrupting `.env`. Fixed by calling `get-parameter` (singular) per name with `>>`.

### Sequencing implications

- New fields in a **new dedicated SSM parameter**: use `env_prefix` directly — no alias needed.
- Fields **already in SSM**: use `Field(validation_alias=AliasChoices("EXISTING_NAME"))` to preserve the deployed env var name while keeping the Python attribute name clean. `AliasChoices` also accepts multiple fallback names, enabling gradual migration (e.g. `AliasChoices("NEW_NAME", "EXISTING_NAME")`).
- Using `Field(alias=...)` is **discouraged** for this purpose: `alias` affects both parsing *and* serialization, which can cause unexpected behaviour during `.model_dump()` calls.
- `env_nested_delimiter` + bulk rename (Option B for IS-07-D) is **not viable** — requires renaming every deployed key simultaneously.

---

## Migration Path

Tracked under IS-07 in [`infrastructure-core-services-cleanup.md`](../../transition/infrastructure-core-services-cleanup.md).

### IS-07-A: Retire `infrastructure/configuration/features/`

For each `modules/<name>` retirement or migration to `packages/<name>`:
1. Delete `infrastructure/configuration/features/<name>.py`.
2. Remove the field from `infrastructure/configuration/settings.py`.
3. If migrating to `packages/<name>`, create `packages/<name>/settings.py` using Pattern B (`Field(validation_alias=AliasChoices(...))` for existing SSM keys). See `settings-singleton.md`.
4. Remove any duplicate fields (e.g., `INCIDENT_CHANNEL`) from integration settings in the **same PR** that retires the legacy module.
5. Each module deletion is independent — do not wait for all to finish.

### IS-07-B: Narrow settings slices for core services

For each provider in `providers.py` passing full `Settings` to a service:
1. Identify which slice is actually used.
2. Update `__init__` to accept that specific type.
3. Update the provider to pass `settings.<section>`.
4. Update tests to construct the service with only the slice.

No env var changes. No SSM changes. Internal refactor only.

### IS-07-C: Enforce settings rules for all new `packages/`

Every new `packages/<name>/settings.py` requires: `@lru_cache(maxsize=1)` provider, `startup_warmup` hookimpl, and correct naming pattern per `settings-singleton.md` (Pattern A with `env_prefix` if a dedicated SSM param exists; Pattern B with `Field(validation_alias=AliasChoices(...))` for migrated legacy fields).

### IS-07-D: Dissolve the central `Settings` aggregator

Once feature settings are removed (IS-07-A), move each remaining sub-settings class to its own `@lru_cache` provider in `providers.py`. The class keeps its existing field names — nothing in SSM changes:

```python
@lru_cache(maxsize=1)
def get_slack_settings() -> SlackSettings:
    return SlackSettings()  # reads SLACK_TOKEN, APP_TOKEN, etc. unchanged
```

Each step is one PR. `settings_map` shrinks by one entry per PR. IS-07-E completes this.

### IS-07-E: `entry.sh` and per-domain secrets

**Phase 1 — Fix `entry.sh`** ✅ Done. Uses `get-parameter` (singular) + `>>` per source. Removes the tab-separator bug and all parameter count limits.

**Phase 2 — Per-domain SSM parameters**: create one SSM parameter per feature domain (e.g., `sre-bot-features`). New package settings use `env_prefix` with plain field names — no aliases for brand-new vars.

**Phase 3 — Secrets Manager for credentials**: move tokens and API keys to Secrets Manager (`sre-bot/slack`, `sre-bot/aws`, `sre-bot/google`). Benefits: 65 KB per secret, per-secret IAM, built-in rotation per service. Fetch via `secretsmanager get-secret-value ... >> ".env"` or use ECS task definition `secrets:` injection. Terraform: replace `aws_ssm_parameter` with `aws_secretsmanager_secret`; swap IAM `ssm:GetParameters` → `secretsmanager:GetSecretValue`.

**Phase 4 — Remove `.env` entirely** (optional): once all values come from ECS native injection, remove `env_file=".env"` from all `SettingsConfigDict` calls. Pydantic-settings reads `os.environ` by default.

---

## Resulting Rules

| Context | Now | After IS-07-D + IS-07-E |
|---------|-----|------------------------|
| HTTP route handlers | `SettingsDep` — unchanged | unchanged |
| Legacy `modules/` and `jobs/` | `get_settings()` — unchanged | unchanged |
| `providers.py` | `get_settings()` → extract slice → pass to constructor | each service calls its own `get_<name>_settings()` |
| Core service `__init__` | accept narrowest `*Settings` type, never `Settings` | same |
| `packages/<name>/` new fields | `env_prefix` in dedicated SSM param (Pattern A) | same — `env_prefix` universally |
| `packages/<name>/` migrated fields | `Field(validation_alias=AliasChoices("EXISTING_NAME"))` (Pattern B) | aliases removed post-rename |
| `infrastructure/configuration/settings.py` | integration + infrastructure only; no feature settings | deleted or `PREFIX`/`LOG_LEVEL`/`GIT_SHA` only |
| Secret storage | SSM StringList parameters + `.env` | Secrets Manager per domain; ECS native injection |

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Feature settings lose startup validation | `startup_warmup` hookimpl preserves fail-fast guarantee |
| Duplicate fields during migration | Accepted temporary state; resolved in the PR that retires the legacy module |
| Service constructor breakage | Internal to infrastructure layer; callers use `get_*` providers |
| Option B (`env_nested_delimiter` rename) attempted | Explicitly rejected; block any PR attempting it |
| Dual-source window during Secrets Manager migration | Keep SSM frozen; cut over only after ECS confirms Secrets Manager injection is stable |
