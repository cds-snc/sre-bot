# Logging Standards (OpenTelemetry + structlog)

**Status**: ✅ CURRENT - Aligned with OpenTelemetry semantic conventions

**Implementation Reference**: `/workspace/app/infrastructure/logging/setup.py`

## Structured Logging Pattern
```python
import structlog

# ✅ Module-level logger (no binding at module level)
logger = structlog.get_logger()

def process_request(user_id: str, group_id: str, request_id: str):
    """Process request with structured logging.
    
    Bind ONLY request-scoped context. Code location (filepath, function, line)
    is added automatically by OpenTelemetry processors.
    """
    # ✅ Bind request-scoped context per-call
    log = logger.bind(user_id=user_id, group_id=group_id, request_id=request_id)
    
    log.info("processing_started")
    # ... do work ...
    log.info("processing_completed", duration_ms=123)
    
    # ❌ WRONG - Never bind code location manually
    # log = logger.bind(component="groups", module="processor")  # Automatic!
```

**FastAPI Routes**:
```python
import structlog
from fastapi import APIRouter
from infrastructure.services import SettingsDep

logger = structlog.get_logger()
router = APIRouter()

@router.post("/add")
def add_member(request: AddMemberRequest, settings: SettingsDep):
    """Add member with request-scoped logging.
    
    OpenTelemetry automatically captures:
    - code.filepath: "api/v1/groups/routes.py"
    - code.function: "add_member"
    - code.lineno: <line number>
    """
    # ✅ Bind only request-scoped context
    log = logger.bind(
        group_id=request.group_id,
        requestor=request.requestor,
        request_id=request.request_id,  # From request headers
    )
    log.info("request_received")
    
    # Process request...
    log.info("request_completed", status="success")
    
    # ❌ WRONG - Never bind endpoint or component manually
    # log = logger.bind(endpoint="/add")  # Automatic via code.function!
```

**Class-Based Services**:
```python
import structlog

class GroupService:
    """Service for group operations."""
    
    def __init__(self):
        # ✅ Module logger (no binding at class level)
        self.logger = structlog.get_logger()
    
    def add_member(self, user_id: str, group_id: str, request_id: str) -> None:
        """Add member to group.
        
        Bind request-scoped context in method scope.
        """
        # ✅ Bind call-scoped context
        log = self.logger.bind(
            user_id=user_id,
            group_id=group_id,
            request_id=request_id,
        )
        log.info("adding_member")
        # ... do work ...
        log.info("member_added")
```

**Utility Functions with Operation Context**:
```python
import structlog

logger = structlog.get_logger()

def execute_api_call(service: str, operation: str, **kwargs) -> dict:
    """Execute external API call with retry logic.
    
    Bind operation context (not request context) for utility functions.
    """
    # ✅ Bind operation-level context
    log = logger.bind(service=service, operation=operation)
    log.info("api_call_started")
    
    for attempt in range(max_retries):
        # ✅ Bind iteration-specific context
        attempt_log = log.bind(attempt=attempt)
        attempt_log.debug("retrying")
        
        try:
            result = call_api(service, operation, **kwargs)
            log.info("api_call_completed", status_code=result.status_code)
            return result
        except Exception as e:
            attempt_log.error("api_call_failed", error=str(e))
```

**Critical Rules**:

**What to Bind**:
- ✅ Request-scoped identifiers: `user_id`, `request_id`, `correlation_id`, `customer_id`
- ✅ Business entities: `group_id`, `member_email`, `resource_id`
- ✅ Operation context: `service`, `operation`, `attempt` (for retries)
- ✅ Dynamic state: `status`, `duration_ms`, `error_code`

**What NOT to Bind** (Automatic via OpenTelemetry):
- ❌ Code location: `code.filepath`, `code.function`, `code.lineno` (automatic)
- ❌ Component/module names: `component=`, `module=` (use code.filepath instead)
- ❌ Endpoint names: `endpoint=` (use code.function instead)
- ❌ Manual namespace: `code_namespace=` (automatic)

**Patterns**:
- ✅ Use `structlog.get_logger()` at module/class level (no arguments)
- ✅ Bind context inside functions/methods (not at module level)
- ✅ Use `.bind()` to create scoped logger for execution context
- ✅ Use structured keys (snake_case) for log fields
- ✅ Log events, not sentences: `"user_created"` not `"User was created"`
- ❌ Never use `print()` for logging
- ❌ Never use Python's `logging` module directly
- ❌ Never log sensitive data (tokens, passwords, PII)
- ❌ Never bind logger at module level (`logger = logger.bind(...)`)
- ❌ Never manually bind code location fields

---

## 1.2 OpenTelemetry Semantic Conventions

**Decision**: Structured logs automatically include OpenTelemetry semantic conventions for code location.

**Automatic Fields** (added by processors):

| Field | Description | Example |
|-------|-------------|---------|
| `code.filepath` | Relative file path from project root | `api/v1/groups/routes.py` |
| `code.function` | Function or method name | `add_member` |
| `code.lineno` | Line number where log call occurred | `42` |
| `timestamp` | ISO 8601 timestamp | `2026-02-05T14:23:45.123Z` |
| `level` | Log level | `info` |
| `event` | Log event name | `request_received` |

**What This Means**:
- Every log entry automatically includes file, function, and line number
- No need to manually specify component, module, or namespace
- Logs are traceable to exact source code location
- Works seamlessly with log aggregation tools (CloudWatch, Datadog, etc.)

**Example Log Output**:
```json
{
  "event": "processing_started",
  "timestamp": "2026-02-05T14:23:45.123Z",
  "level": "info",
  "code.filepath": "modules/groups/service.py",
  "code.function": "add_member",
  "code.lineno": 45,
  "user_id": "user@example.com",
  "group_id": "abc123",
  "request_id": "req-xyz789"
}
```

---

## 1.3 Log Levels

**Decision**: Standard log levels with specific use cases and scenarios.

| Level | When to Use | Examples |
|-------|-------------|----------|
| `debug` | **Development only** - Detailed diagnostic information | Cache hits/misses, internal state transitions, step-by-step flow |
| `info` | **Normal operations** - Confirmation things work as expected | Request received/completed, resource created/updated, background job started/finished |
| `warning` | **Degraded but functional** - Unexpected but recoverable | Retry attempts, rate limit approaching, fallback to defaults, deprecated feature used |
| `error` | **Operation failed** - Requires investigation but app continues | API call failed, validation error, database timeout, external service unavailable |
| `critical` | **System failure** - Application may be unable to continue | Database unreachable, configuration invalid, required service down |

**Level Selection Examples**:

```python
import structlog

logger = structlog.get_logger()

def process_transaction(user_id: str, transaction_id: str):
    log = logger.bind(user_id=user_id, transaction_id=transaction_id)
    
    # DEBUG (Development only - detailed diagnostics)
    log.debug("cache_lookup", key=f"transaction:{transaction_id}", found=True)
    log.debug("query_executed", duration_ms=45)
    
    # INFO (Production normal operations)
    log.info("transaction_started")
    log.info("transaction_completed", amount=100.00, currency="USD")
    
    # WARNING (Recoverable issues)
    log.warning("api_retry_attempt", attempt=2, max_attempts=3, service="payment_api")
    log.warning("rate_limit_approaching", current=450, limit=500, window_seconds=60)
    
    # ERROR (Failures requiring attention)
    log.error("payment_api_failed", status_code=500, retry_after=60)
    log.error("validation_failed", field="amount", reason="exceeds_limit")
    
    # CRITICAL (System-wide failures)
    log.critical("database_connection_failed", error="connection_timeout", db="postgres")
    log.critical("required_service_unavailable", service="payment_provider")
```

**Rules**:
- ✅ `info` for all successful write operations (creates audit trail)
- ✅ `info` for request lifecycle events (received, processing, completed)
- ✅ `warning` for retries, degraded state, circuit breaker events
- ✅ `error` for failures that don't stop the application
- ✅ `critical` for failures that may prevent application startup/operation
- ✅ Include context fields relevant to the event (status_code, attempt, duration_ms)
- ❌ Never log at `debug` in production (performance impact)
- ❌ Never use `info` for high-frequency read operations (use metrics instead)
- ❌ Never log different levels for the same event type (be consistent)
