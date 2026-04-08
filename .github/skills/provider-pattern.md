# Provider Pattern

**Reference**: `docs/decisions/tier-1-foundation/application-lifecycle/04-provider-discovery.md`

## Pattern

Providers use `@lru_cache(maxsize=1)` singleton pattern. Services receive dependencies via `__init__`.

---

## Services Layer Architecture

Three files form the services layer — do not collapse them:

| File | Purpose |
|------|---------|
| `infrastructure/services/providers.py` | All `@lru_cache(maxsize=1)` factory functions. The only place where service instances are constructed. |
| `infrastructure/services/dependencies.py` | FastAPI DI wiring only: `XDep = Annotated[X, Depends(get_x)]`. No logic. |
| `infrastructure/services/__init__.py` | Re-export surface. Imports and re-exports from the two files above. Nothing is defined here. |

**Adding a new service requires changes to all three files** — provider function in `providers.py`, type alias in `dependencies.py`, and re-export + `__all__` entry in `__init__.py`.

---

## Provider Function Template

```python
# infrastructure/services/providers.py
from functools import lru_cache

@lru_cache(maxsize=1)
def get_my_service() -> MyService:
    """Get singleton service instance."""
    settings = get_settings()
    return MyService(my_settings=settings.my_section)
```

**Rules**:
- Always `@lru_cache(maxsize=1)`, never bare `@lru_cache` (default maxsize=128 is semantically wrong for singletons).
- Extract and pass only the relevant settings *slice* (`settings.aws`, `settings.slack`, etc.) — never pass the full `Settings` object to a service that doesn't need the entire configuration tree.
- Call `get_settings()` inside the function body, not at module level.
- No business logic, no conditional imports at module level.

---

## Service Class Template

```python
# infrastructure/my_service/service.py
from infrastructure.configuration.infrastructure.my_section import MySectionSettings

class MyService:
    def __init__(self, my_settings: MySectionSettings):
        self.settings = my_settings
```

**Pattern**: Receive the narrowest settings type required in `__init__`. Core services (`AWSClients`, `SlackClientFacade`, etc.) accept only their own settings section, not the application-wide `Settings` object. The provider function in `providers.py` is the one place that extracts the slice.

For **feature packages** (`packages/<name>/`), do not import from `infrastructure.services` for settings at all — define a local `BaseSettings` class. All fields use `Field(alias=...)` to control the exact env var name:

```python
# packages/my_feature/settings.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class MyFeatureSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )
    # New env vars: use PACKAGE_NAME_ prefix in the alias
    some_value: str = Field(alias="MY_FEATURE_SOME_VALUE")
    # Env vars already in SSM from a legacy module: keep the deployed name
    legacy_channel: str = Field(default="", alias="EXISTING_CHANNEL_VAR")

@lru_cache(maxsize=1)
def get_my_feature_settings() -> MyFeatureSettings:
    return MyFeatureSettings()
```

Then consume it inside the package via a hookimpl or directly:

```python
# packages/my_feature/__init__.py
from packages.my_feature.settings import get_my_feature_settings

@hookimpl
def startup_warmup(logger) -> None:
    s = get_my_feature_settings()  # raises ValidationError if misconfigured
    logger.info("my_feature_settings_loaded", some_value=s.some_value)
```

---

## Re-Export `__init__.py` Pattern

`infrastructure/services/__init__.py` is a re-export surface. Flake8 F401 (imported but unused) is suppressed for all `__init__.py` files via `.flake8`:

```ini
per-file-ignores =
    */__init__.py:F401
```

Every public name must appear in `__all__`:

```python
# infrastructure/services/__init__.py
from infrastructure.services.providers import get_my_service, t
from infrastructure.services.dependencies import MyServiceDep

__all__ = [
    "MyServiceDep",
    "get_my_service",
    "t",
    ...
]
```

Do **not** define functions in `__init__.py`. If a helper belongs in the services layer, put it in `providers.py`.

---

## ECS Parallel Tasks — Singleton Scope

`lru_cache` is **per-process**. Each ECS task is a separate OS process, so:
- Each task has its own independent service instances.
- Singletons are not shared across tasks — this is correct behavior.
- State mutations on a singleton (e.g., `TranslationService._is_initialized`) are local to that task's process and do not affect other tasks.

```
ECS Task A (process 1)          ECS Task B (process 2)
  lru_cache                       lru_cache
    get_settings() → Settings_A     get_settings() → Settings_B  ← independent
    get_translation_service()        get_translation_service()    ← independent
```

Within a single task, all threads share the same `lru_cache`. Python's `lru_cache` uses an internal lock, so concurrent first-call races are safe.

---

## Lifecycled Services (two-phase init)

Some services are constructed safely (`__init__`) but require an explicit initialization call before use (`initialize()`). `TranslationService` is the canonical example.

`lru_cache` gives you the same *object* on every call, but does **not** run `initialize()`. The lifespan is responsible for calling `initialize()` before routes serve traffic.

```python
# server/lifespan.py — correct startup order
translation_service = get_translation_service()   # construction only
translation_service.initialize(resources=...)     # explicit lifecycle step
translation_service.health_check()               # validate before accepting traffic
```

Never call `initialize()` inside the `@lru_cache` provider function — that would make construction have side effects and break test isolation.

---

## Test Isolation

`lru_cache` singletons persist between test functions in the same process. Tests that need a fresh instance must call `cache_clear()`:

```python
# conftest.py or per-test setup
import pytest
from infrastructure.services.providers import get_translation_service, get_settings

@pytest.fixture(autouse=True)
def clear_service_caches():
    yield
    get_translation_service.cache_clear()
    get_settings.cache_clear()
```

Only clear caches that the test actually exercises; clearing all caches in every test is slow.

---

## Forbidden Patterns

```python
# ❌ Bare @lru_cache without maxsize (semantically wrong for singletons)
@lru_cache
def get_service():
    return MyService()

# ❌ Provider without @lru_cache (creates new instance on every call)
def get_service():
    return MyService()

# ❌ Passing the full Settings object to a service that needs only a slice
@lru_cache(maxsize=1)
def get_slack_client() -> SlackClientFacade:
    settings = get_settings()
    return SlackClientFacade(settings=settings)  # WRONG — pass settings.slack only

# ❌ Service self-fetching dependencies
class MyService:
    def __init__(self):
        self.settings = get_settings()  # WRONG — receive via parameter

# ❌ Define logic or functions in __init__.py
# infrastructure/services/__init__.py
def get_slack_provider():     # WRONG — put this in providers.py
    return get_platform_service().get_provider("slack")

# ❌ Call initialize() inside @lru_cache provider
@lru_cache(maxsize=1)
def get_translation_service():
    svc = TranslationService()
    svc.initialize(...)   # WRONG — side effect in constructor breaks test isolation
    return svc

# ❌ Feature package importing get_settings() from infrastructure.services
# packages/my_feature/service.py
from infrastructure.services import get_settings   # WRONG — use packages.my_feature.settings
settings = get_settings().my_feature_section

# ❌ New env var in a feature package without a namespaced alias
class MyFeatureSettings(BaseSettings):
    api_key: str                   # WRONG — use Field(alias="MY_FEATURE_API_KEY")

# ❌ Module-level provider registries (deprecated — use pluggy hookimpls)
_PROVIDERS: dict = {}
def load_providers():                              # WRONG — register via hookimpl instead
    _PROVIDERS["google"] = GoogleProvider()
```

---

## Pre-Implementation Checklist

Before creating a **core infrastructure** provider/service:

1. ☐ Provider function has `@lru_cache(maxsize=1)`
2. ☐ Provider calls `get_settings()` inside function body and passes only the relevant settings *slice*
3. ☐ Service receives its own settings type in `__init__` — not the application-wide `Settings`
4. ☐ Name added to `dependencies.py` (`XDep = Annotated[X, Depends(get_x)]`)
5. ☐ Name re-exported in `__init__.py` and added to `__all__`
6. ☐ If service has lifecycle (`initialize()`), lifespan calls it — not the provider function

Before creating a **feature package** (`packages/<name>/`) setting:

1. ☐ `packages/<name>/settings.py` defines a `BaseSettings` subclass
2. ☐ Every field uses `Field(alias="PACKAGE_NAME_FIELD")` — new vars get `PACKAGE_NAME_` prefix; vars already deployed in SSM keep their exact existing name
3. ☐ A `@lru_cache(maxsize=1)` provider function inside `settings.py` returns the instance
4. ☐ The package `__init__.py` hookimpl (`startup_warmup`) calls the local provider to validate at startup
5. ☐ The central `infrastructure/configuration/settings.py` is **not** modified
6. ☐ `infrastructure.services.get_settings` is **not** imported inside the feature package
