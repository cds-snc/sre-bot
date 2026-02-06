# Operation Result Pattern

All integration operations return `OperationResult` and accept `request_id` for logging.

---

## Creating OperationResult

```python
import structlog
from infrastructure.operations import OperationResult

logger = structlog.get_logger()

def list_accounts(request_id: str) -> OperationResult:
    log = logger.bind(request_id=request_id)
    log.info("listing_accounts")
    try:
        accounts = fetch_accounts()
        return OperationResult.success(data=accounts)
    except RateLimitError as exc:
        log.warning("rate_limited")
        return OperationResult.transient_error(
            message=str(exc),
            error_code="RATE_LIMIT",
            retry_after=60,
        )
    except Exception as exc:
        log.error("list_failed", error=str(exc))
        return OperationResult.permanent_error(
            message=str(exc),
            error_code="LIST_FAILED",
        )
```

Rules:
- ✅ Return `OperationResult` from integration functions
- ✅ Use `OperationResult.success|transient_error|permanent_error`
- ✅ Include `error_code` for failures
- ✅ Log with request-scoped context
- ❌ Never return `None` or plain dicts
- ❌ Never raise exceptions from integration functions

---

## Handling OperationResult

**Check success and extract data safely**:

```python
def sync_accounts(request_id: str) -> list[dict]:
    result = list_accounts(request_id)
    
    if result.is_success:
        # Safe data extraction with null coalescing
        return result.data if result.data else []
    
    # Log failure details for debugging
    log = logger.bind(request_id=request_id)
    log.error(
        "sync_failed",
        status=result.status,
        message=result.message,
        error_code=result.error_code,
    )
    return []
```

**Differentiate handling by error type**:

```python
def process_user(user_id: str) -> dict:
    result = get_user(user_id)
    
    if result.is_success:
        return result.data or {}
    
    # Handle transient errors (may retry)
    if result.status == OperationStatus.TRANSIENT_ERROR:
        log.warning("transient_error", retry_after=result.retry_after)
        # Could implement retry logic here
        return {}
    
    # Handle permanent errors (don't retry)
    log.error("permanent_error", error_code=result.error_code)
    return {}
```

Rules:
- ✅ Check `result.is_success` property
- ✅ Use `if result.data` to handle None cases
- ✅ Log `status`, `message`, `error_code` on failure
- ✅ Differentiate handling by OperationStatus
- ✅ Use `retry_after` to implement backoff
- ❌ Never call `result.is_success()`
- ❌ Never directly access `result.data` without null check
- ❌ Never swallow errors silently

---

## OperationStatus Classification

Use `OperationStatus` to categorize failures and drive caller behavior.

```python
from infrastructure.operations import OperationResult, OperationStatus

def get_resource(resource_id: str, request_id: str) -> OperationResult:
    log = logger.bind(request_id=request_id)
    try:
        resource = fetch_resource(resource_id)
        if resource is None:
            return OperationResult.error(
                status=OperationStatus.NOT_FOUND,
                message="Resource not found",
                error_code="RESOURCE_NOT_FOUND",
            )
        return OperationResult.success(data=resource)
    
    except TimeoutError as exc:
        log.warning("upstream_timeout")
        return OperationResult.error(
            status=OperationStatus.TRANSIENT_ERROR,
            message=str(exc),
            error_code="UPSTREAM_TIMEOUT",
            retry_after=30,
        )
    
    except Exception as exc:
        log.error("unexpected_error", error=str(exc))
        return OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message=str(exc),
            error_code="FETCH_FAILED",
        )
```

Rules:
- ✅ Use `OperationStatus.SUCCESS` for successful operations
- ✅ Use `OperationStatus.TRANSIENT_ERROR` for retryable failures (timeouts, rate limits)
- ✅ Use `OperationStatus.PERMANENT_ERROR` for non-retryable failures
- ✅ Include `retry_after` (seconds) for transient errors
- ✅ Use `NOT_FOUND` for 404-like conditions
- ❌ Never return `TRANSIENT_ERROR` without `retry_after`
- ❌ Never treat permanent errors as retryable