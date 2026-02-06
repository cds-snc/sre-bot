# No Async/Await Pattern

**Enforcement**: CRITICAL

## Rule

SRE Bot uses synchronous code only. No `async def` or `await` except in FastAPI lifespan.

---

## Correct Patterns

```python
# ✅ Synchronous functions
def process_data(data: dict) -> OperationResult:
    """Standard synchronous function."""
    result = perform_operation(data)
    return OperationResult.success(data=result)

# ✅ Synchronous class methods
class UserService:
    def create_user(self, email: str) -> User:
        """Synchronous method."""
        user = User(email=email)
        return user

# ✅ FastAPI routes (sync)
@router.get("/users")
def list_users(settings: SettingsDep):
    """Synchronous route handler."""
    return {"users": []}

# ✅ Jobs (sync)
def sync_groups_job():
    """Synchronous job."""
    providers = get_active_providers()
    for provider in providers.values():
        provider.sync_groups()
```

---

## Exception: Lifespan Only

```python
# ✅ ONLY place async allowed
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Async context manager for lifespan."""
    initialize_all()  # Sync function call
    yield
    shutdown_all()  # Sync function call
```

**Reason**: FastAPI requires `async def` for lifespan. But functions called inside are sync.

---

## Forbidden Patterns

```python
# ❌ Async functions
async def process_data(data: dict):  # WRONG
    result = await some_operation()
    return result

# ❌ Async class methods
class UserService:
    async def create_user(self, email: str):  # WRONG
        user = await create_in_db(email)
        return user

# ❌ Async routes
@router.get("/users")
async def list_users():  # WRONG
    users = await get_users()
    return users

# ❌ await keyword
def process():
    result = await operation()  # WRONG - no await in sync function
```

---

## Why No Async

1. **Simplicity**: Sync code easier to understand and debug
2. **No I/O Concurrency**: App doesn't need concurrent I/O operations
3. **Thread-based**: Background work uses threads (Socket Mode, scheduled tasks)
4. **Consistency**: All business logic follows same pattern

---

## Thread-Based Concurrency

```python
# ✅ Use threading for background work
import threading

def start_background_task():
    thread = threading.Thread(
        target=long_running_task,
        daemon=True,
    )
    thread.start()

def long_running_task():
    """Synchronous function running in thread."""
    while True:
        process_batch()
        time.sleep(60)
```

**Pattern**: Threads for background work, not async/await.

---

## Pre-Implementation Checklist

Before generating code:

1. ☐ No `async def` (except lifespan)
2. ☐ No `await` keyword
3. ☐ No `asyncio` imports
4. ☐ Use `threading` for background work
5. ☐ All routes are `def`, not `async def`
6. ☐ All services are `def`, not `async def`

**If async detected outside lifespan, REJECT code generation.**
