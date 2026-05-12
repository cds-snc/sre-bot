---
name: settings-singleton
description: Apply partitioned settings and singleton provider patterns; use when adding or refactoring settings and provider wiring.
---

## Settings Ownership

| Domain | Location | Type |
|--------|----------|------|
| Infrastructure | `app/infrastructure/` | `BaseSettings` |
| Integration | `app/integrations/` | `BaseSettings` |
| Feature | `app/packages/<feature>/settings.py` | `BaseSettings` |

## Provider Pattern

One `BaseSettings` + `@lru_cache(maxsize=1)` provider per domain:

```python
@lru_cache(maxsize=1)
def get_settings() -> MySettings:
    return MySettings()
```

Inject narrow slices into services, never full Settings tree:

```python
async def __init__(self, config: MySettings.Section):
    self.timeout = config.timeout
```

## Rules

- **No nested BaseSettings.** Root owns env vars; nested sections use BaseModel.
- **No key duplication** across settings modules.
- **Fail-fast:** invalid config terminates startup.
- **Don't instantiate in routes/services.** Inject via Depends.
- **Clear @lru_cache between tests** via autouse fixture.

## Anti-patterns

- Adding package settings to central aggregator.
- Broad Settings objects passed to services.
- Repeated settings instantiation.
