---
adr_id: ADR-0031
title: "Request ID Propagation"
status: Accepted
decision_type: Standard
tier: Tier-3
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - Platform Engineering
supersedes: []
superseded_by: []
related_records:
  - ADR-0029
  - ADR-0039
related_packages: []
review_state: stale
---
# Request ID Propagation

**Status**: ACCEPTED — April 2026  
**Tier**: 3 — Cross-cutting

---

## Context

All logging examples across this project bind `request_id` as a first-class log field. However, no document specifies:

1. **Where** `request_id` originates (generated vs. forwarded from a client header).
2. **How** it flows through the call stack — currently passed as a function argument everywhere, which is verbose and breaks down in background tasks.
3. **Which API** manages per-request context — structlog's `contextvars` API is the correct mechanism but is absent from all existing patterns.

---

## Decision

Use `structlog.contextvars` to bind `request_id` once per request in middleware. All code in the request call chain inherits the binding automatically without explicit parameter passing.

---

## Implementation

### 1. Middleware — Bind at the ASGI boundary

```python
# app/server/middleware/request_id.py
import uuid
import structlog
from starlette.types import ASGIApp, Receive, Scope, Send


class RequestIdMiddleware:
    """Pure ASGI middleware — binds request_id to structlog contextvars."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Clear previous request context (critical for connection reuse)
        structlog.contextvars.clear_contextvars()

        # Honour upstream request ID (load balancer, API gateway, tracing header)
        headers = dict(scope.get("headers", []))
        incoming = headers.get(b"x-request-id", b"").decode()
        request_id = incoming if incoming else str(uuid.uuid4())

        structlog.contextvars.bind_contextvars(request_id=request_id)

        await self.app(scope, receive, send)
```

Register in lifespan setup **before** all other middleware to ensure every downstream component sees the binding:

```python
# app/server/main.py
from app.server.middleware.request_id import RequestIdMiddleware

app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)
```

---

### 2. Logging — No explicit parameter needed

Once the middleware binds `request_id`, structlog processors emit it automatically on every log event in the same async task.

```python
# ✅ CORRECT — request_id appears automatically
import structlog

logger = structlog.get_logger()

def add_group_member(group_id: str, member_email: str) -> None:
    log = logger.bind(group_id=group_id, member_email=member_email)
    log.info("adding_member")  # emits: request_id=<uuid> group_id=... member_email=...

# ❌ AVOID — manual threading of request_id through every call signature
def add_group_member(group_id: str, member_email: str, request_id: str) -> None:
    log = logger.bind(group_id=group_id, request_id=request_id)
    log.info("adding_member")
```

---

### 3. Integration operations — include request_id in provider calls

External integration functions may still accept `request_id` explicitly when they need to pass it to the remote API (e.g. as a correlation header or audit field). In that case, read it from `structlog.contextvars`:

```python
# infrastructure/clients/google_workspace/groups.py
import structlog

def list_members(group_id: str) -> list[dict]:
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "")
    # pass to Google API as X-Goog-Request-Reason or similar audit field
    ...
```

---

### 4. Background tasks — explicitly re-bind

`contextvars` are **not** inherited by `asyncio.create_task()` or APScheduler jobs. Re-bind explicitly before the task body:

```python
import asyncio
import uuid
import structlog

async def spawn_sync_job(trigger_request_id: str) -> None:
    async def _job() -> None:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=trigger_request_id,
            job="sync_groups",
        )
        await sync_groups()

    asyncio.create_task(_job())
```

---

## Request ID Origin Rules

| Source | Behaviour |
|---|---|
| `X-Request-ID` header present | Use the forwarded value as-is |
| No header | Generate `uuid.uuid4()` |
| ALB / CloudFront / API Gateway | These headers are forwarded by default — no extra config needed |

---

## Rules

- ✅ Register `RequestIdMiddleware` as the outermost application middleware
- ✅ Use `structlog.contextvars.bind_contextvars` — never `logger.bind` at module scope
- ✅ Call `clear_contextvars()` at the start of each request (middleware does this)
- ✅ Re-bind `request_id` explicitly in background tasks and APScheduler jobs
- ✅ Honour incoming `X-Request-ID` for end-to-end traceability
- ❌ Do not pass `request_id` as a function argument through service layers — use `contextvars`
- ❌ Do not bind `request_id` at module level — context is per-request
- ❌ Do not assume `contextvars` propagate across `asyncio.create_task()` boundaries automatically
