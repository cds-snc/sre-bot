---
adr_id: ADR-0039
title: "Middleware & Request Pipeline"
status: Superseded
decision_type: Feature
tier: Tier-4
date_created: unknown
last_updated: 2026-04-30
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by:
  - ADR-0063
related_records:
  - ADR-0031
  - ADR-0038
related_packages: []
review_state: stale
---
# Middleware & Request Pipeline

## Context

Middleware execution order affects performance and correctness. CORS must run first; authentication must run before handlers. Custom error handlers must be registered consistently. High-throughput paths can suffer from BaseHTTPMiddleware buffering.

## Decision

Middleware order (outer to inner): CORS, Rate limiting, Request logging, Error handling, Authentication. Use pure ASGI middleware for high-throughput paths to avoid response buffering. Custom exception handlers are registered via app.exception_handler.

## Consequences

- ✅ Consistent middleware ordering across all deployments
- ✅ High-throughput paths avoid buffering overhead
- ✅ Error handling is centralized and predictable
- ✅ Custom handlers can implement domain-specific logic
- ⚠️ Pure ASGI middleware requires careful async handling

---

## Middleware Order

**Decision**: Middleware execution follows specific order.

**Order** (outer to inner):
1. CORS middleware
2. Rate limiting
3. Request logging
4. Error handling
5. Authentication

**Implementation**:
```python
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 1. CORS (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Rate limiting
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 3-5. Custom middleware (inner)
# Add as needed
```

**Rules**:
- ✅ CORS must be outermost
- ✅ Rate limiting before authentication
- ✅ Error handling near application core
- ❌ Don't reorder without understanding impact

> **`BaseHTTPMiddleware` performance caveat**: `app.add_middleware(SomeMiddleware)` uses Starlette's `BaseHTTPMiddleware` by default. This wraps the ASGI app in a way that buffers the full response body for streaming responses, causing measurable overhead on large payloads. For simple request/response interception (e.g. adding headers, logging) it is acceptable. For high-throughput or streaming paths, prefer a pure ASGI middleware:
>
> ```python
> class RequestIdMiddleware:
>     def __init__(self, app):
>         self.app = app
>
>     async def __call__(self, scope, receive, send):
>         if scope["type"] == "http":
>             import uuid, structlog
>             request_id = scope.get("headers", {}).get(b"x-request-id", str(uuid.uuid4()).encode()).decode()
>             structlog.contextvars.bind_contextvars(request_id=request_id)
>         await self.app(scope, receive, send)
>
> app.add_middleware(RequestIdMiddleware)  # Pure ASGI, no buffering
> ```

---

## Custom Error Handlers

**Decision**: Register custom handlers.

**Implementation**:
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc)},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error_type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )
```

**Rules**:
- ✅ Register handlers at app level
- ✅ Return consistent error format
- ✅ Include appropriate status codes
- ❌ Don't catch exceptions in middleware