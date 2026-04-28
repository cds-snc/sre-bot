---
adr_id: ADR-0009
title: "FastAPI Lifespan Pattern"
status: Accepted
decision_type: Principle
tier: Tier-1
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - Platform Engineering
supersedes: []
superseded_by: []
related_records:
  - ADR-0001
  - ADR-0005
  - ADR-0011
  - ADR-0016
related_packages: []
review_state: stale
---
# FastAPI Lifespan Pattern

## Context

FastAPI's startup/shutdown events are deprecated when a lifespan context manager is provided. We need a unified, async-safe startup/shutdown mechanism that integrates with the 7-phase initialization sequence.

## Decision

Use FastAPI's `@asynccontextmanager`-based lifespan pattern for all startup and shutdown logic. Code before `yield` executes on startup; code after `yield` executes on shutdown. Replace all `app.add_event_handler("startup", ...)` calls.

## Consequences

- ✅ Single unified startup/shutdown entry point
- ✅ Supports async initialization natively
- ✅ Clear startup/shutdown separation via yield
- ⚠️ All initialization logic must fit into one lifespan function or be called from it

---

## Implementation

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    log = logger.bind(phase="startup")
    
    # STARTUP: Code before yield
    log.info("application_starting")
    
    settings = initialize_configuration()
    initialize_infrastructure(settings)
    providers = initialize_providers(settings)
    
    app.state.settings = settings
    app.state.providers = providers
    
    log.info("application_ready")
    
    yield  # Application accepts HTTP requests
    
    # SHUTDOWN: Code after yield
    log = logger.bind(phase="shutdown")
    log.info("application_shutting_down")
    await shutdown_services(app)
    log.info("application_stopped")

app = FastAPI(
    title="SRE Bot",
    lifespan=lifespan,
)

# Router and route registration after app creation
from api import router
app.include_router(router)
```

---

## Execution Timeline

**Module Import**: Lifespan function defined, NOT executed.

**Startup** (`uvicorn main:app`):
1. FastAPI calls `lifespan(app).__aenter__()`
2. Code before `yield` executes
3. Application ready for requests

**Shutdown** (SIGTERM):
1. FastAPI calls `lifespan(app).__aexit__()`
2. Code after `yield` executes
3. Process terminates

---

## State Storage

Store lifespan resources in `app.state` for graceful shutdown teardown only. Route handlers must always use `Depends()` — never access `request.app.state` in handlers.

```python
# During startup — store for graceful shutdown reference only
app.state.settings = settings
app.state.providers = providers
```

```python
# ✅ CORRECT: routes use Depends()
from infrastructure.services import SettingsDep

@router.get("/example")
def example(settings: SettingsDep):
    return {"region": settings.aws.aws_region}

# ❌ FORBIDDEN: accessing app.state in a route handler
from fastapi import Request

def handler(request: Request):
    settings = request.app.state.settings  # WRONG
```

---

## Rules

- ✅ Use `@asynccontextmanager` decorator
- ✅ Code before `yield` = startup
- ✅ Code after `yield` = shutdown
- ✅ Store lifespan resources in `app.state` (shutdown teardown reference only)
- ❌ NEVER: `app.add_event_handler("startup", ...)`
- ❌ NEVER: `app.add_event_handler("shutdown", ...)`
- ❌ NEVER: access `request.app.state` in route handlers — use `Depends()` instead
