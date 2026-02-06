# Rate Limiting

## Route-Level Rate Limiting

**Decision**: Use SlowAPI.

**Implementation**:
```python
# api/dependencies/rate_limits.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# In routes
from api.dependencies.rate_limits import get_limiter

router = APIRouter()
limiter = get_limiter()

@router.get("/health")
@limiter.limit("50/minute")
def health_check(request: Request):
    return {"status": "ok"}
```

**Rules**:
- ✅ Apply to public endpoints
- ✅ Use `@limiter.limit("N/period")` decorator
- ✅ Require `Request` parameter when using limiter
- ❌ Don't over-limit critical endpoints (health checks)

---

## Custom Rate Limit Keys

**Decision**: Use custom key functions.

**Implementation**:
```python
def sentinel_key_func(request: Request):
    # Skip rate limiting for sentinel (monitoring)
    if request.headers.get("X-Sentinel-Source"):
        return None  # No rate limit
    return get_remote_address(request)

# Setup
from slowapi import Limiter
limiter = Limiter(key_func=sentinel_key_func)
```

**Rules**:
- ✅ Return `None` to skip rate limiting
- ✅ Return unique key per client
- ✅ Use for monitoring/health checks
- ❌ Don't bypass for regular users

---

## Rate Limit Error Handling

**Decision**: Custom 429 handler.

**Implementation**:
```python
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"message": "Rate limit exceeded"},
    )

# Register handler
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
```

**Rules**:
- ✅ Return 429 status code
- ✅ Include clear error message
- ✅ Register handler at app level
- ❌ Don't include retry timing (security)

---

## Monitoring Rate Limits

**Decision**: Log rate limit events.

**Implementation**:
```python
from slowapi import Limiter
from structlog import get_logger

logger = get_logger()

def log_rate_limit(request: Request):
    logger.info("Rate limit exceeded", client_ip=request.client.host, path=request.url.path)

limiter = Limiter(key_func=get_remote_address)
limiter._storage._on_limit_reached = log_rate_limit
```