# Dependency Injection Pattern

## Layering

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

FastAPI dependency injection via `Annotated[T, Depends(get_X)]`.

```python
from typing import Annotated
from fastapi import Depends
from infrastructure.configuration import Settings
from infrastructure.idempotency.service import IdempotencyService
from infrastructure.services.providers import get_settings, get_idempotency_service

SettingsDep = Annotated[Settings, Depends(get_settings)]
IdempotencyServiceDep = Annotated[IdempotencyService, Depends(get_idempotency_service)]
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