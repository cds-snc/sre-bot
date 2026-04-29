---
adr_id: ADR-0003
title: "Dependency Injection Pattern"
status: Superseded
decision_type: Principle
tier: Tier-1
date_created: unknown
last_updated: 2026-04-29
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by:
  - ADR-0048
related_records:
  - ADR-0001
  - ADR-0002
  - ADR-0004
  - ADR-0018
  - ADR-0024
  - ADR-0033
related_packages: []
review_state: stale
---
# Dependency Injection Pattern

## Context

Application code spans routes (sync/async), jobs, and modules—all requiring consistent access to services. Services must be testable with overridable dependencies. A clear layer boundary between application code and infrastructure is essential.

## Decision

Enforce a three-layer architecture with DI at the boundary: Application → Dependency Injection Layer (providers + type aliases) → Infrastructure Core. All services created via `@lru_cache` provider functions; all service injection via `Annotated[T, Depends(...)]` type aliases.

## Consequences

- ✅ Single, consistent service creation and access pattern
- ✅ Testable via FastAPI's `override_dependency()`
- ✅ Works seamlessly for both sync and async handlers
- ⚠️ Requires defining type aliases in `infrastructure/services/dependencies.py`
- ⚠️ Route and business code cannot instantiate services directly

## Implementation

### Layering

```
APPLICATION (api/, modules/, jobs/)
  ↓ imports infrastructure/services
DEPENDENCY INJECTION (infrastructure/services/)
  ↓ providers.py (@lru_cache), dependencies.py (type aliases)
INFRASTRUCTURE CORE (configuration, clients, operations, ...)
```

---

## Provider Functions

All services created by `@lru_cache` providers.

```python
from functools import lru_cache
from infrastructure.configuration import Settings
from infrastructure.idempotency.service import IdempotencyService

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

@lru_cache(maxsize=1)
def get_idempotency_service() -> IdempotencyService:
    settings = get_settings()
    return IdempotencyService(settings=settings)
```

**Anti-patterns**:
```python
# ❌ FORBIDDEN: Missing cache
def get_idempotency_service() -> IdempotencyService:
    return IdempotencyService(settings=get_settings())

# ❌ FORBIDDEN: Service fetches settings
class IdempotencyService:
    def __init__(self):
        self.settings = get_settings()
```

Rules:
- ✅ Providers use `@lru_cache(maxsize=1)`
- ✅ Providers inject all dependencies via constructor
- ❌ Never call providers inside service constructors
- ❌ Never call `get_settings()` inside service constructors

---

## Dependency Type Aliases

FastAPI dependency injection via `Annotated[T, Depends(get_X)]`. Works seamlessly with both sync and async handlers.

```python
from typing import Annotated
from fastapi import Depends
from infrastructure.configuration import Settings
from infrastructure.idempotency.service import IdempotencyService
from infrastructure.services.providers import get_settings, get_idempotency_service

SettingsDep = Annotated[Settings, Depends(get_settings)]
IdempotencyServiceDep = Annotated[IdempotencyService, Depends(get_idempotency_service)]

# Use in sync handlers
@router.post("/sync-endpoint")
def sync_handler(settings: SettingsDep, service: IdempotencyServiceDep):
    return service.process(settings)

# Use in async handlers — same aliases work
@router.post("/async-endpoint")
async def async_handler(settings: SettingsDep, service: IdempotencyServiceDep):
    return service.process(settings)
```

**Anti-patterns**:
```python
# ❌ FORBIDDEN: Alias defined in route file
from typing import Annotated
from fastapi import Depends

SettingsDep = Annotated[Settings, Depends(get_settings)]
```

Rules:
- ✅ Define aliases only in `infrastructure/services/dependencies.py`
- ✅ Export aliases from `infrastructure/services/__init__.py`
- ✅ Name with `Dep` suffix
- ❌ Never define aliases in modules/routes

---

## Public Exports

Application code imports only from `infrastructure.services`.

```python
from infrastructure.services import SettingsDep, IdempotencyServiceDep
from infrastructure.services import get_settings, get_idempotency_service
```

Rules:
- ✅ Single import surface: `infrastructure.services`
- ❌ Never import directly from `providers.py` or `dependencies.py`