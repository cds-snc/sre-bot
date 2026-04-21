# Settings Singleton Pattern

**Reference**: `docs/decisions/tier-1-foundation/07-settings-partitioned-model.md` (supersedes ADR-02 rules for feature packages)

## Two-Tier Model

Settings are split by ownership:

| Tier | Owner | Where it lives | Access pattern |
|------|-------|----------------|----------------|
| **Core** — integration credentials + infrastructure behavior | `infrastructure/` | `infrastructure/configuration/settings.py` | `get_settings()` in `providers.py`; `SettingsDep` in routes |
| **Feature** — business config for one package | `packages/<name>/` | `packages/<name>/settings.py` | `get_<name>_settings()` defined in the same file |

Feature settings **never** appear in the central `Settings` class. The central class contains only integration credentials (`SlackSettings`, `AwsSettings`, etc.) and infrastructure behavior (`RetrySettings`, `IdempotencySettings`, etc.).

---

## Core Settings Usage

### Provider Function (Already Exists — Do Not Modify)

```python
# infrastructure/services/providers.py
from functools import lru_cache
from infrastructure.configuration import Settings

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
```

Providers extract a slice and pass it to the service — never pass the whole `Settings`:

```python
@lru_cache(maxsize=1)
def get_aws_clients() -> AWSClients:
    settings = get_settings()
    return AWSClients(aws_settings=settings.aws)   # ← slice only
```

### Routes

```python
# modules/*/controllers.py
from infrastructure.services import SettingsDep

@router.get("/config")
def get_config(settings: SettingsDep):
    return {"region": settings.aws.aws_region}
```

**Pattern**: `SettingsDep` type annotation for FastAPI DI.

### Legacy modules / jobs

```python
# modules/*/service.py  or  jobs/*.py
from infrastructure.services import get_settings

def sync_job():
    settings = get_settings()   # call once, store in local variable
    if settings.PREFIX != "":
        return
```

---

## Feature Package Settings

Every `packages/<name>/` defines its own settings in `packages/<name>/settings.py`. Choose the pattern based on whether env vars already exist in production SSM.

**Decision rule:**
- New package, no existing SSM keys → **Pattern A** (`env_prefix`, dedicated SSM parameter)
- Migrating an existing module with keys already in SSM → **Pattern B** (`Field(alias=...)` for each existing key)
- Feature with multiple sub-features sharing one namespace → **Pattern C** (single root `BaseSettings` with nested `BaseModel` slices)

### Pattern A — New package, no existing env vars

Use `env_prefix` directly. All env vars for this package go into a **new dedicated SSM parameter** (e.g., `sre-bot-my-feature`). Add one line to `entry.sh` and one `aws_ssm_parameter` Terraform resource.

```sh
# entry.sh — add one line per new SSM parameter source
aws ssm get-parameter --region ca-central-1 --with-decryption \
  --name sre-bot-my-feature --query 'Parameter.Value' --output text >> ".env"
```

```python
# packages/my_feature/settings.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class MyFeatureSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
        env_prefix="MY_FEATURE_",
    )
    api_key: str              # reads MY_FEATURE_API_KEY
    dry_run: bool = False     # reads MY_FEATURE_DRY_RUN

@lru_cache(maxsize=1)
def get_my_feature_settings() -> MyFeatureSettings:
    return MyFeatureSettings()
```

No `Field(alias=...)` needed. The `env_prefix` handles the namespace for all fields.

### Pattern B — Migrating an existing module with env vars already in SSM

Do **not** set `env_prefix` on the class. Use `Field(alias=)` for every field to map to the exact deployed env var name. The SSM parameters do not change.

```python
# packages/incident/settings.py  (migrated from modules/incident)
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class IncidentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )
    # Existing SSM keys — alias must exactly match the deployed var name.
    # Do NOT change the alias until the SSM parameter is updated.
    channel: str = Field(default="", alias="INCIDENT_CHANNEL")
    security_group_id: str = Field(default="", alias="SLACK_SECURITY_USER_GROUP_ID")
    # New fields not yet in SSM also use an explicit alias to establish namespace.
    retry_limit: int = Field(default=3, alias="INCIDENT_RETRY_LIMIT")

@lru_cache(maxsize=1)
def get_incident_settings() -> IncidentSettings:
    return IncidentSettings()
```

A field that also exists in `SlackSettings` (e.g., `INCIDENT_CHANNEL`) is an accepted temporary duplicate during migration. Remove the legacy field from the integration settings class in the **same PR** that retires the old `modules/incident` code.

### Pattern C — Feature with multiple sub-features (used by `packages/access/`)

When one top-level namespace (`ACCESS_`) contains settings for several sub-features (sync, requests, catalog), consolidate into a **single root `BaseSettings`** with **plain `BaseModel` slices**. One env read, tree-shaped access.

**Mechanism**: `env_prefix` + `env_nested_delimiter="_"` + `env_nested_max_split=1` + `case_sensitive=False`.

`env_nested_max_split=1` means the split happens only at the sub-feature boundary:
`ACCESS_SYNC_RECONCILIATION_SCHEDULE` → strip prefix → `SYNC_RECONCILIATION_SCHEDULE` → split once → group `sync`, field `reconciliation_schedule`.

`case_sensitive=False` is **required** with this mechanism: pydantic-settings uses field names (lowercase `sync`) to build the key prefix, and must match the uppercase OS env vars case-insensitively.

```python
# packages/access/common/settings.py
from functools import lru_cache
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class AccessSyncSettings(BaseModel):       # plain BaseModel, not BaseSettings
    enabled: bool = False                  # ACCESS_SYNC_ENABLED
    job_ttl_seconds: int = 86400           # ACCESS_SYNC_JOB_TTL_SECONDS

class AccessRequestsSettings(BaseModel):
    enabled: bool = False                  # ACCESS_REQUESTS_ENABLED

class AccessSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ACCESS_",
        env_nested_delimiter="_",
        env_nested_max_split=1,
        case_sensitive=False,              # required — see above
        extra="ignore",
        env_file=".env",
    )
    sync: AccessSyncSettings = Field(default_factory=AccessSyncSettings)
    requests: AccessRequestsSettings = Field(default_factory=AccessRequestsSettings)

@lru_cache(maxsize=1)
def get_access_settings() -> AccessSettings:
    return AccessSettings()
```

**Slice providers for FastAPI `Depends`** — thin functions (no `@lru_cache` needed since root is already cached):

```python
# packages/access/sync/providers.py
def get_access_sync_settings() -> AccessSyncSettings:
    return get_access_settings().sync
```

**Sub-features** pass their own slice to services, not the root object:

```python
settings = get_access_settings()
return SyncService(settings=settings.sync)   # ✅ — narrow type
```

**Testing**: `AccessSyncSettings` is a plain `BaseModel`. Construct directly with overrides:

```python
def _make(**overrides) -> AccessSyncSettings:
    return AccessSyncSettings(**overrides)

# For env-var loading tests, use the root:
settings = AccessSettings(_env_file=None).sync
```

**Adding a new sub-feature**:
1. Add `AccessAdminSettings(BaseModel)` to `common/settings.py`
2. Add `admin: AccessAdminSettings = Field(default_factory=AccessAdminSettings)` to `AccessSettings`
3. Define env vars as `ACCESS_ADMIN_{FIELD}`
4. No new `BaseSettings` subclass, no new provider, no new `entry.sh` line

---

```python
# packages/my_feature/__init__.py
from packages.my_feature.settings import get_my_feature_settings

@hookimpl
def startup_warmup(logger) -> None:
    s = get_my_feature_settings()   # ValidationError → startup aborts (fail-fast)
    logger.info("my_feature_settings_loaded", dry_run=s.dry_run)
```

The feature's service receives its own settings type:

```python
# packages/my_feature/service.py
from packages.my_feature.settings import MyFeatureSettings

class MyFeatureService:
    def __init__(self, settings: MyFeatureSettings):
        self._settings = settings
```

---

## Forbidden Patterns

```python
# ❌ Direct instantiation of the central Settings
from infrastructure.configuration import Settings
settings = Settings()  # WRONG

# ❌ Feature package importing central get_settings
from infrastructure.services import get_settings    # WRONG inside packages/<name>/
settings = get_settings().some_feature_section      # WRONG

# ❌ Feature settings added to infrastructure/configuration/settings.py
class Settings(BaseSettings):
    my_feature: MyFeatureSettings   # WRONG — feature settings belong in the package

# ❌ Passing full Settings to a service that needs only a slice
return MyService(settings=get_settings())           # WRONG — pass settings.my_section

# ❌ Core service accepting the full Settings
class AWSClients:
    def __init__(self, settings: Settings):         # WRONG — accept AwsSettings instead
        self._region = settings.aws.aws_region

# ❌ Pattern A class with no env_prefix — env var ownership is ambiguous
class MyFeatureSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", ...)
    api_key: str                                    # WRONG — which service owns API_KEY?

# ❌ Pattern B class dropping the alias for an existing SSM key
class IncidentSettings(BaseSettings):
    channel: str                                    # WRONG — INCIDENT_CHANNEL is already in SSM

# ❌ Changing an existing alias to rename a deployed SSM key
channel: str = Field(alias="INCIDENT__CHANNEL")    # WRONG — the old key breaks in prod

# ❌ Call get_settings repeatedly in one scope
def process():
    region = get_settings().aws.aws_region
    env = get_settings().environment                # WRONG — call once, store
```

---

## Environment Variables

```bash
# Core settings (existing SSM keys — do not rename without a deployment plan)
SLACK_TOKEN=xoxb-token
AWS_REGION=ca-central-1

# Pattern A: new package with dedicated SSM param — vars follow env_prefix naming
MY_FEATURE_API_KEY=secret
MY_FEATURE_DRY_RUN=true

# Pattern B: migrated module — vars keep their original deployed name
INCIDENT_CHANNEL=C01234567
```

**Rule — Pattern A (new package):** set `env_prefix="PACKAGE_NAME_"` on `SettingsConfigDict`. Plain field names; no aliases. Vars go into a new dedicated SSM parameter.

**Rule — Pattern B (migration):** no `env_prefix` on the class. Every field uses `Field(alias="EXACT_DEPLOYED_NAME")`. Do not change an alias value without updating the SSM parameter in the same deployment.

---

## Validation

Both tiers validate at construction time. `ValidationError` terminates the process.

- Core: validated on the first `get_settings()` call in `lifespan()`.
- Feature: validated in `startup_warmup` hookimpl, called from lifespan before traffic is accepted.

Both give the same fail-fast guarantee: misconfigured services never start.

