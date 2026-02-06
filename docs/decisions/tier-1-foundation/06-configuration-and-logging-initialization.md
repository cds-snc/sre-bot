# Configuration and Logging Initialization

Core services are divided into two categories based on initialization timing requirements: **bootstrap-time core services** and **lazy-loaded managed services**.

---

## Bootstrap-Time Core Services

Configuration and logging are initialized at **module import time**, before FastAPI lifespan startup.

### Configuration (pydantic_settings)

**Initialization point**: Module import
- [infrastructure/configuration/settings.py](../../../app/infrastructure/configuration/settings.py) aggregates all domain-specific settings
- [infrastructure/services/providers.py](../../../app/infrastructure/services/providers.py) provides singleton via `@lru_cache` decorator
- [server/server.py](../../../app/server/server.py) line 11: `settings = get_settings()` executed at module load

**Usage at module import time**:
- Line 25: CORS middleware configuration depends on `settings.is_production`
- `allow_origins` list selected based on production/development environment

**Initialization in lifespan**:
- Settings instance retrieved again (returns cached copy from `@lru_cache`)
- Stored in `app.state.settings` for request handler access
- No reconfiguration occurs; structure is fixed at import time

### Logging (structlog)

**Initialization point**: Lifespan startup
- [infrastructure/logging/setup.py](../../../app/infrastructure/logging/setup.py) function `configure_logging(settings)` called in lifespan
- [server/lifespan.py](../../../app/server/lifespan.py) line 167: `logger = _get_logger(settings)` executed before first log
- Configuration requires Settings instance as dependency

**Usage before lifespan**:
- Cannot emit logs at module import time; structlog not yet configured
- Processor pipeline not established until `configure_logging()` called

**Initialization in lifespan**:
- [server/lifespan.py](../../../app/server/lifespan.py) Phase 1 executes before any event handler activation
- Establishes processor pipeline with OpenTelemetry semantic conventions
- Detects test environment and suppresses output accordingly
- Stored in `app.state.logger` for direct access; also accessible via `structlog.get_logger()`

### Middleware Impact

**Timing**:
1. Module import: Settings singleton created
2. Module import: Middleware added to FastAPI app (depends on settings)
3. Lifespan startup: Logging configured
4. Lifespan startup: Request context binding available for request-scoped correlation IDs
5. Request handling: Middleware executes; logging already configured

**Critical dependency**: CORS middleware configuration cannot delay until lifespan because middleware is registered at app creation time (step 2). Settings must be available at step 1.

**Logging dependency**: Middleware and handlers can emit logs during request processing because logging is configured before `yield` in lifespan (step 3). Request context binding ([infrastructure/logging/context.py](../../../app/infrastructure/logging/context.py)) allows middleware to inject correlation IDs.

---

## Lazy-Loaded Managed Services

Other core infrastructure services are created on-demand via dependency injection.

### Service Examples

- IdentityService: User identity resolution
- JWKSManager: JSON Web Key Set caching
- AWSClients: AWS API clients
- GoogleWorkspaceClients: Google API clients
- MaxMindClient: Geolocation service
- EventDispatcher: In-process event bus
- TranslationService: i18n
- IdempotencyService: Request deduplication
- ResilienceService: Circuit breaker patterns
- NotificationService: Multi-platform notifications
- CommandService: Slack/Teams command routing
- PersistenceService: Database access
- PlatformService: Platform integration abstraction

### Initialization Pattern

All are in [infrastructure/services/providers.py](../../../app/infrastructure/services/providers.py):
- Each service factory function uses `@lru_cache` decorator
- Called first time: Creates singleton instance
- Subsequent calls: Returns cached instance
- Dependency chain: Services depend on Settings, resolved lazily

Example:
```python
@lru_cache
def get_identity_service() -> IdentityService:
    settings = get_settings()  # Returns cached singleton
    # Create and cache service...
    return service
```

### Lifecycle

- **Creation time**: First request to handler that requires service
- **Scope**: Application lifetime (single instance per process)
- **Shutdown**: Not explicitly managed; rely on Python garbage collection

### Why Not Bootstrap Services

- High initialization cost (external API calls, background threads, state allocation)
- Not all services required in all execution modes (e.g., AWS clients if AWS integration disabled)
- Feature packages (vertical modules) declare dependencies explicitly; lazy loading satisfies dependencies on-demand
- No requirement to coordinate among services at startup

Example lazy-loaded dependency:
```python
# Feature module
from infrastructure.services import EventDispatcherDep

async def process_event(dispatcher: EventDispatcherDep):
    # EventDispatcher created here if not already cached
    dispatcher.dispatch(event)
```

---

## Initialization Sequence

**Module Import** (Synchronous)
1. Settings singleton created via `get_settings()` (no config file I/O; uses environment variables)
2. FastAPI instance created with lifespan context manager reference
3. Rate limiter initialized and registered as exception handler
4. CORS middleware configured using `settings.is_production`
5. Rate limiter middleware configured
6. API router included
7. Module import complete; app ready for lifespan

**Lifespan Startup** (Async)
- Phase 1: Logging configured via `configure_logging(settings)`
- Phase 2-7: Providers, event handlers, Slack socket mode, scheduled tasks

**Request Handling**
- Middleware executes (CORS, rate limiting)
- Request context binding available
- Lazy services created on first handler access
- Response returned

**Lifespan Shutdown** (Async)
- Scheduled tasks stopped
- Socket mode connection closed
- Providers and state cleaned up

---

## Dependencies and Order Constraints

| Component | Depends On | Time |
|-----------|-----------|------|
| FastAPI app creation | Settings | Module import |
| CORS middleware | Settings.is_production | Module import |
| Rate limiting | (none) | Module import |
| Logging setup | Settings | Lifespan startup |
| Event handlers | Logging, Settings | Lifespan startup |
| Lazy services | Settings | Request handling (on-demand) |

---

## Code Evidence

**Configuration at module import**:
- `/workspace/app/server/server.py` lines 11, 25-32

**Logging in lifespan**:
- `/workspace/app/server/lifespan.py` lines 167-168

**Settings singleton**:
- `/workspace/app/infrastructure/services/providers.py` lines 25-44

**Lazy service factories**:
- `/workspace/app/infrastructure/services/providers.py` lines 47-150

**Middleware configuration**:
- `/workspace/app/api/dependencies/rate_limits.py` lines 18-26

**Logging configuration**:
- `/workspace/app/infrastructure/logging/setup.py` lines 105-217

**Lifespan phases**:
- `/workspace/app/server/lifespan.py` lines 100-202
