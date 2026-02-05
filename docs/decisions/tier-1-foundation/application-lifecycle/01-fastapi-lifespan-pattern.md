# FastAPI Lifespan Pattern

Use FastAPI `lifespan` context manager for startup/shutdown. Replace `app.add_event_handler("startup", ...)`.

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

Store initialization state in `app.state`:

```python
# During startup
app.state.settings = settings
app.state.providers = providers

# Access in request handlers
from fastapi import Request

def handler(request: Request):
    settings = request.app.state.settings
```

---

## Rules

- ✅ Use `@asynccontextmanager` decorator
- ✅ Code before `yield` = startup
- ✅ Code after `yield` = shutdown
- ✅ Store state in `app.state`
- ❌ NEVER: `app.add_event_handler("startup", ...)`
- ❌ NEVER: `app.add_event_handler("shutdown", ...)`
