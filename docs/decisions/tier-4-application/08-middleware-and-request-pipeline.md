# Middleware & Request Pipeline

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