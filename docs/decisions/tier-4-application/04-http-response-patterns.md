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

## Error Response Consistency

**Decision**: All error responses include structured information.

**Required Fields**:
- `detail` (string): Human-readable error message from OperationResult
- `error_code` (optional string): Code from `result.error_code` for categorization
- HTTP status code: Mapped from `result.status`

**Implementation**:
```python
import structlog
from fastapi import HTTPException
from infrastructure.operations import OperationStatus

logger = structlog.get_logger()

@router.post("/members/add")
def add_member(request: AddMemberRequest, settings: SettingsDep):
    """Add member to group with structured error responses."""
    log = logger.bind(group_id=request.group_id, member_email=request.member_email)
    log.info("request_received")
    
    result = add_member_operation(request)
    
    # ✅ CORRECT - Map to HTTPException with all status variants
    if not result.is_success:
        error_detail = {
            "message": result.message,
            "error_code": result.error_code or "OPERATION_FAILED"
        }
        
        if result.status == OperationStatus.UNAUTHORIZED:
            log.error("auth_failed", error_code=result.error_code)
            raise HTTPException(status_code=401, detail=error_detail["message"])
        elif result.status == OperationStatus.NOT_FOUND:
            log.warning("resource_not_found", error_code=result.error_code)
            raise HTTPException(status_code=404, detail=error_detail["message"])
        elif result.status == OperationStatus.TRANSIENT_ERROR:
            log.warning("transient_error", error_code=result.error_code,
                       retry_after=getattr(result, 'retry_after', None))
            raise HTTPException(status_code=503, detail=error_detail["message"])
        else:  # PERMANENT_ERROR
            log.error("operation_failed", error_code=result.error_code)
            raise HTTPException(status_code=400, detail=error_detail["message"])
    
    log.info("request_completed", status="success")
    return {"member_email": request.member_email, "added": True}
```

**Rules**:
- ✅ Include `error_code` from OperationResult for client-side routing
- ✅ Use `result.message` for human-readable detail in HTTPException
- ✅ Log structured context including error codes for troubleshooting
- ✅ Handle rate-limit scenario with `retry_after` in logs
- ✅ Never raise HTTPException(500) for handled operation failures
- ❌ Don't expose internal stack traces in HTTP responses
- ❌ Don't log secrets in error context
- ❌ Don't use generic "Operation failed" without error_code
