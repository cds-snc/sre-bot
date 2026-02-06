# Core Architectural Principles

## Synchronous-First Execution

All application code must be synchronous (`def`, not `async def`). Async is allowed only for FastAPI lifespan.

```python
# ✅ CORRECT
def handle_command(ctx: CommandContext) -> CommandResponse:
    return process_request()

# ❌ FORBIDDEN
async def handle_command(ctx: CommandContext) -> CommandResponse:
    return await process_request()
```

---

## Stateless Design

No in-memory state shared across requests. AWS ECS runs multiple parallel tasks; all shared state lives in DynamoDB.

- ✅ DynamoDB for tracking and idempotency
- ✅ `@lru_cache` for process-wide singletons (one per ECS task)
- ❌ Module-level variables for request state
- ❌ In-memory caches shared across requests

---

## Top-Level Imports Only

ALL imports at module level. No lazy imports inside functions.

```python
# ✅ CORRECT
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from infrastructure.configuration import Settings

from infrastructure.operations import OperationResult
from infrastructure.services import get_settings

# ❌ FORBIDDEN
def process():
    from infrastructure.services import get_settings  # WRONG
```

Exception: `TYPE_CHECKING` imports to avoid circular dependencies.

---

## Mandatory Dependency Injection

All infrastructure services receive dependencies via constructor. Infrastructure services must not import other infrastructure services directly.

```python
# ✅ CORRECT
class MyService:
    def __init__(self, settings: Settings):
        self.settings = settings

# ❌ FORBIDDEN
class MyService:
    def __init__(self):
        self.settings = get_settings()  # WRONG - Bypasses DI
```

---

## Security by Default

Never log sensitive data. Credentials in environment variables only.

```python
import structlog

logger = structlog.get_logger()

def authenticate(user_id: str, token: str) -> None:
    log = logger.bind(user_id=user_id)
    log.info("user_authenticated")

    # ❌ FORBIDDEN
    log.info("auth", token=token)
```

- ✅ Log user IDs and operation context
- ❌ Log tokens, API keys, passwords, or secrets
