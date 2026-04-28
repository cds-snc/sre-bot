---
adr_id: ADR-0001
title: "Core Architectural Principles"
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
  - ADR-0002
  - ADR-0003
  - ADR-0004
  - ADR-0005
  - ADR-0009
related_packages: []
review_state: stale
---
# Core Architectural Principles

## Context

This project must run reliably on Python 3.12+ with modern async patterns, strict type safety, and safe concurrent request handling across multiple ECS tasks. We require clear boundaries between application logic, dependency injection, and infrastructure layers to maintain testability and scalability.

## Decision

We establish five core architectural principles governing all code:

### Framework and Version Requirements

This project requires:
- **Python 3.12+** — all typing and async features assume 3.12 minimum.
- **Pydantic v2 / pydantic-settings v2** — `SettingsConfigDict`, `model_config`, `@field_validator`, `@model_validator` all use v2 APIs. Never use v1 patterns (`class Config`, `validator`, `root_validator`).
- **FastAPI 0.100+** — lifespan context manager, `Annotated[T, Depends()]` syntax.

---

## Incremental Async Migration

The codebase is transitioning from synchronous-first to async-native. **Both sync and async handlers coexist safely in FastAPI.**

**For new code and refactors, follow this priority:**

1. **Async (`async def`)** — I/O-bound operations with async-native libraries (aiohttp, asyncpg, aioboto3). Avoids thread pool consumption. **Preferred for new work.**
2. **Sync (`def`)** — CPU-bound logic, existing code, or when no async client library exists. Runs in thread pool without blocking event loop.
3. **Both types** — Can mix safely in one application. FastAPI dependency injection supports both.

**Guidelines:**

- ✅ **Use async for:** Database queries, HTTP calls, external API requests, file I/O
- ✅ **Use sync for:** Business logic, data transformation, CPU-bound processing, legacy code
- ✅ **Both are valid:** No architectural penalty for using either; choose based on I/O presence
- ⚠️ **Design for async:** When refactoring sync code, consider whether an async-native library exists for any external I/O. Use it if available.
- ❌ **Avoid:** CPU-intensive operations in async handlers (no `await` necessary, doesn't improve concurrency)

**Examples:**

```python
# ✅ ASYNC: I/O-bound (HTTP call)
async def fetch_user(user_id: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.example.com/users/{user_id}") as resp:
            return await resp.json()

# ✅ SYNC: Business logic
def validate_command(command: CommandContext) -> bool:
    return command.user_id in ALLOWED_USERS and command.action in ALLOWED_ACTIONS

# ✅ ASYNC: Database query (async-native client)
async def get_group_members(group_id: str) -> list:
    async with get_db_pool() as pool:
        return await pool.fetch("SELECT * FROM members WHERE group_id = $1", group_id)

# ✅ SYNC: Legacy code, no I/O
def parse_legacy_format(data: str) -> dict:
    # Existing sync-only logic, no changes needed
    return parse_data(data)
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
