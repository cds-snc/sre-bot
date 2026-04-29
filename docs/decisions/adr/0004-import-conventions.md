---
adr_id: ADR-0004
title: "Import Conventions"
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
  - ADR-0003
  - ADR-0019
related_packages: []
review_state: stale
---
# Import Conventions

## Context

Clear import boundaries prevent circular dependencies, make layer violations obvious, and support testability. Application code must not access low-level infrastructure clients directly.

## Decision

Enforce strict import hierarchy: Application can import from infrastructure/services only; Services layer can import infrastructure and configuration; Infrastructure Core packages are isolated from Application and from each other (siblings only).

## Consequences

- ✅ Clear enforcement of DI pattern (ADR-0003)
- ✅ Prevents circular dependencies
- ✅ Makes layer violations obvious in code review
- ⚠️ Requires discipline to avoid `infrastructure.clients` imports in application code

## Implementation

### Import Hierarchy

| Layer | CAN Import From | CANNOT Import From |
|-------|----------------|-------------------|
| **Application** (api/, modules/, jobs/) | `infrastructure.services`, `infrastructure.operations`, `infrastructure.models` | `infrastructure.configuration`, `infrastructure.clients.*` |
| **Services** (infrastructure/services/) | `infrastructure.configuration`, `infrastructure.clients`, all infra packages | Application layer |
| **Infrastructure Core** | Sibling packages, `structlog` | Other infra services directly, application layer |

---

## Application Code (Routes — Sync or Async)

```python
import structlog
from fastapi import APIRouter
from infrastructure.services import SettingsDep, MyServiceDep
from infrastructure.operations import OperationResult
from modules.groups.api.schemas import AddMemberRequest, Response

logger = structlog.get_logger()
router = APIRouter()

# Sync route (thread pool execution)
@router.post("/add")
def add_member(
    request: AddMemberRequest,
    settings: SettingsDep,  # Dependency injection
    service: MyServiceDep,
) -> Response:
    log = logger.bind(group_id=request.group_id)
    log.info("adding_member")
    return Response(id="123")

# Async route (event loop) — preferred for I/O operations
@router.post("/add-async")
async def add_member_async(
    request: AddMemberRequest,
    settings: SettingsDep,  # Same alias works
    service: MyServiceDep,
) -> Response:
    log = logger.bind(group_id=request.group_id)
    log.info("adding_member_async")
    return Response(id="123")
```

---

## Application Code (Jobs/Modules)

```python
import structlog
from infrastructure.services import get_settings, get_my_service
from infrastructure.operations import OperationResult

logger = structlog.get_logger()

def background_job():
    settings = get_settings()  # Cached singleton
    service = get_my_service()  # Cached singleton
    
    log = logger.bind(job="background_job")
    log.info("job_started")
    return OperationResult.success()
```

---

## Infrastructure Services

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.configuration import Settings

import structlog

logger = structlog.get_logger()

class MyService:
    def __init__(self, settings: "Settings") -> None:
        self.settings = settings
        logger.info("service_initialized")
    
    def do_work(self) -> str:
        return "done"
```

---

## Infrastructure Providers

```python
from functools import lru_cache
from infrastructure.configuration import Settings
from infrastructure.clients.aws import AWSClients
from my_service import MyService

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

@lru_cache(maxsize=1)
def get_my_service() -> MyService:
    settings = get_settings()  # Provider fetches singleton
    aws = AWSClients(settings=settings)  # Provider creates deps
    return MyService(settings=settings)  # Provider injects
```

---

## Anti-patterns

```python
# ❌ FORBIDDEN: Import inside function
def handler():
    from infrastructure.services import get_settings
    return get_settings().environment

# ❌ FORBIDDEN: Direct configuration import in application code
from infrastructure.configuration import Settings
settings = Settings()
```

---

## Rules

- ✅ All imports at module top level
- ✅ Infrastructure packages use `get_settings()` from `infrastructure.services.providers`
- ✅ Application code uses `SettingsDep` or `get_settings()` from `infrastructure.services`
- ✅ Services receive deps via constructor
- ✅ Use `TYPE_CHECKING` for circular import avoidance
- ✅ Both sync (`def`) and async (`async def`) handlers import identically; FastAPI handles execution
- ❌ NEVER: Lazy imports (imports inside functions)
- ❌ NEVER: Infrastructure services importing each other directly
- ❌ NEVER: Application code importing from `infrastructure.configuration`
