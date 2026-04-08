# HTTP Response Patterns

**Reference**: See [03-operation-result-pattern.md](../tier-2-infrastructure/03-operation-result-pattern.md) for comprehensive OperationResult patterns.

---

## OperationResult to HTTP Mapping

**Decision**: Convert `OperationResult` to HTTP responses.

**Status Code Mapping**:
```python
OperationStatus.SUCCESS           → 200 OK (or 201 Created)
OperationStatus.TRANSIENT_ERROR   → 503 Service Unavailable
OperationStatus.PERMANENT_ERROR   → 400 Bad Request
OperationStatus.UNAUTHORIZED      → 401 Unauthorized
OperationStatus.NOT_FOUND         → 404 Not Found
```

**Implementation with Exhaustive Pattern Matching** (Python 3.10+):
```python
import structlog
from fastapi import HTTPException
from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.services import SettingsDep

logger = structlog.get_logger()
router = APIRouter()

@router.get("/accounts")
def list_accounts(settings: SettingsDep):
    """List AWS accounts with exhaustive error handling."""
    log = logger.bind(operation="list_accounts")
    log.info("request_received")
    
    result = get_aws_accounts()
    
    # ✅ CORRECT - Exhaustive match on all status variants
    match result.status:
        case OperationStatus.SUCCESS:
            log.info("request_completed", count=len(result.data))
            return {"accounts": result.data}
        
        case OperationStatus.NOT_FOUND:
            log.warning("accounts_not_found", error_code=result.error_code)
            raise HTTPException(status_code=404, detail=result.message)
        
        case OperationStatus.UNAUTHORIZED:
            log.error("auth_failed", error_code=result.error_code)
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        case OperationStatus.TRANSIENT_ERROR:
            log.warning("transient_error", error_code=result.error_code, 
                       retry_after=getattr(result, 'retry_after', None))
            raise HTTPException(status_code=503, detail=result.message)
        
        case OperationStatus.PERMANENT_ERROR:
            log.error("operation_failed", error_code=result.error_code)
            raise HTTPException(status_code=400, detail=result.message)
```

**Alternative: Early Exit Pattern** (when match/case not available):
```python
@router.get("/accounts")
def list_accounts(settings: SettingsDep):
    result = get_aws_accounts()
    
    # ✅ CORRECT - Check each status explicitly
    if result.status == OperationStatus.SUCCESS:
        return {"accounts": result.data}
    elif result.status == OperationStatus.NOT_FOUND:
        raise HTTPException(status_code=404, detail=result.message)
    elif result.status == OperationStatus.UNAUTHORIZED:
        raise HTTPException(status_code=401, detail="Authentication failed")
    elif result.status == OperationStatus.TRANSIENT_ERROR:
        raise HTTPException(status_code=503, detail=result.message)
    else:  # OperationStatus.PERMANENT_ERROR
        raise HTTPException(status_code=400, detail=result.message)
```

**Rules**:
- ✅ Check `.is_success` property (not method) to gate success path
- ✅ Use exhaustive `match` statements (Python 3.10+) or explicit if/elif chains
- ✅ Map each `OperationStatus` to appropriate HTTP status code
- ✅ Include error code in response detail or log for client troubleshooting
- ✅ Log status-specific context (e.g., `retry_after` for transient errors)
- ✅ Never expose sensitive internal error details
- ❌ Never return raw `OperationResult` from routes
- ❌ Never use generic 500 for known status codes (use specific codes above)
- ❌ Never skip status variants (mypy enforces exhaustiveness with match)

---

## Error Mapping Helper

**Decision**: Extract OperationResult → HTTP status code mapping into a private `_to_public_error` function. This keeps route handlers readable, ensures the mapping is applied consistently across all endpoints in a module, and prevents internal error details from leaking into responses.

```python
from infrastructure.operations import OperationResult, OperationStatus


def _to_public_error(result: OperationResult) -> tuple[int, str]:
    """Map an OperationResult error to a safe HTTP status code and message.

    Never expose raw internal messages directly. Return a caller-safe string.
    """
    if result.status == OperationStatus.NOT_FOUND:
        return 404, result.message or "Resource not found"
    if result.status == OperationStatus.UNAUTHORIZED:
        return 403, "Not authorized"
    if result.status == OperationStatus.PERMANENT_ERROR:
        return 400, result.message or "Request could not be completed"
    # TRANSIENT_ERROR and any unexpected status → 500
    return 500, "An internal error occurred"


@router.post("/actions", response_model=ActionResponse)
def action_endpoint(request: ActionRequest, service: ...) -> ActionResponse:
    result = service.do_action(param=request.param)

    if result.is_success:
        return ActionResponse(success=True, data=result.data)

    status_code, detail = _to_public_error(result)
    if status_code >= 500:
        log.error("action_failed", error=result.message, error_code=result.error_code)
    else:
        log.warning("action_failed", error=result.message, error_code=result.error_code)
    raise HTTPException(status_code=status_code, detail=detail)
```

**Rules**:
- ✅ One `_to_public_error` per route module — shared across all handlers in the file
- ✅ Log `result.message` and `result.error_code` internally before discarding them
- ✅ Return a caller-safe string from `_to_public_error` — never `result.message` directly for 5xx responses
- ✅ Log at `error` level for 5xx, `warning` for 4xx
- ❌ Do not inline the full status→code mapping in every handler
- ❌ Do not expose stack traces or internal error codes in the HTTP response body
