---
adr_id: ADR-0018
title: "Service Wrapper Pattern"
status: Superseded
decision_type: Standard
tier: Tier-2
date_created: unknown
last_updated: 2026-04-29
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by:
  - ADR-0056
  - ADR-0077
related_records:
  - ADR-0002
  - ADR-0003
  - ADR-0019
  - ADR-0056
  - ADR-0077
related_packages: []
review_state: superseded
---
# Service Wrapper Pattern

## Context

Infrastructure services need consistent patterns for dependency injection and isolation. Services should not instantiate their own settings or import other services directly, ensuring testability and loose coupling.

## Decision

Infrastructure services receive `settings` as a constructor parameter (injected by providers). Services do not instantiate settings, call `get_settings()`, or import other infrastructure services directly. All dependencies are wired via providers.

## Consequences

- ✅ Settings are validated once and shared across services
- ✅ Services are independently testable with mock settings/dependencies
- ✅ Dependency ordering is explicit and centralized in providers
- ⚠️ Requires disciplined use of TYPE_CHECKING for type hints

---

## Constructor Contract

Infrastructure services receive a `settings` instance as the first required parameter. Services do not instantiate settings and do not call `get_settings()`.

```python
from typing import TYPE_CHECKING
import structlog

if TYPE_CHECKING:
    from infrastructure.configuration import Settings

logger = structlog.get_logger()

class TranslationService:
    def __init__(self, settings: "Settings") -> None:
        self.settings = settings

    def translate(self, key: str, user_id: str) -> str:
        log = logger.bind(user_id=user_id, translation_key=key)
        log.debug("translating")
        return "result"
```

**Anti-patterns**:

```python
# ❌ FORBIDDEN: Direct Settings import in services
from infrastructure.configuration import Settings

class MyService:
    def __init__(self):
        self.settings = Settings()

# ❌ FORBIDDEN: Services call get_settings()
from infrastructure.services import get_settings

class MyService:
    def __init__(self):
        self.settings = get_settings()
```

Rules:

- ✅ `Settings` class imported only under `TYPE_CHECKING` in services
- ✅ `settings` instance injected via provider
- ❌ Services never instantiate `Settings`
- ❌ Services never call `get_settings()`

---

## Service Isolation

Infrastructure services do not import other infrastructure services directly; all dependencies injected via constructor.

```python
from typing import TYPE_CHECKING
import structlog

if TYPE_CHECKING:
    from infrastructure.configuration import Settings
    from infrastructure.idempotency.cache import IdempotencyCache

logger = structlog.get_logger()

class NotificationService:
    def __init__(self, settings: "Settings", cache: "IdempotencyCache") -> None:
        self.settings = settings
        self.cache = cache
```

**Anti-patterns**:

```python
# ❌ FORBIDDEN: Service importing another service
from infrastructure.notifications.service import NotificationService
```

Rules:

- ✅ Dependencies wired in providers
- ❌ Services import other services

---

## Provider Wiring

Providers are the only place allowed to instantiate `Settings`.

```python
from functools import lru_cache
from infrastructure.configuration import Settings
from infrastructure.notifications.service import NotificationService
from infrastructure.idempotency.cache import IdempotencyCache

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

@lru_cache(maxsize=1)
def get_idempotency_cache() -> IdempotencyCache:
    settings = get_settings()
    return IdempotencyCache(table_name=settings.idempotency.table_name)

@lru_cache(maxsize=1)
def get_notification_service() -> NotificationService:
    settings = get_settings()
    cache = get_idempotency_cache()
    return NotificationService(settings=settings, cache=cache)
```

Rules:

- ✅ Providers use `@lru_cache(maxsize=1)`
- ✅ Providers inject dependencies into services
