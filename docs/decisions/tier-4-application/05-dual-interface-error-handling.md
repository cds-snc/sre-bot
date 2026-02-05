# Dual-Interface Error Handling

## API Error Response Pattern

**Decision**: API endpoints return HTTP status codes.

**Implementation**:
```python
# api/v1/groups/routes.py
from fastapi import APIRouter, HTTPException
from infrastructure.operations import OperationResult, OperationStatus

@router.post("/add")
def add_member_api(request: AddMemberRequest) -> AddMemberResponse:
    """API endpoint returns HTTP status codes."""
    result = add_member_to_group(request)
    
    # ✅ Map OperationStatus to HTTP status codes
    if not result.is_success:
        if result.status == OperationStatus.NOT_FOUND:
            raise HTTPException(
                status_code=404,
                detail={"error_code": "GROUP_NOT_FOUND", "message": result.message}
            )
        elif result.status == OperationStatus.UNAUTHORIZED:
            raise HTTPException(
                status_code=401,
                detail={"error_code": "UNAUTHORIZED", "message": result.message}
            )
        elif result.status == OperationStatus.PERMANENT_ERROR:
            raise HTTPException(
                status_code=400,
                detail={"error_code": result.error_code, "message": result.message}
            )
        else:  # TRANSIENT_ERROR
            raise HTTPException(
                status_code=503,
                detail={"error_code": "SERVICE_UNAVAILABLE", "message": result.message}
            )
    
    # ✅ Success returns 200 with JSON payload
    return AddMemberResponse(
        group_id=result.data["group_id"],
        member_email=result.data["member_email"],
        added_at=result.data["added_at"]
    )
```

**HTTP Status Code Mapping**:
| OperationStatus | HTTP Status | Use Case |
|----------------|-------------|----------|
| `SUCCESS` | 200 OK | Operation completed successfully |
| `NOT_FOUND` | 404 Not Found | Resource doesn't exist |
| `UNAUTHORIZED` | 401 Unauthorized | Permission denied |
| `PERMANENT_ERROR` | 400 Bad Request | Validation error, cannot retry |
| `TRANSIENT_ERROR` | 503 Service Unavailable | Network error, can retry |

**Rules**:
- ✅ Use `HTTPException` for all API errors
- ✅ Include `error_code` and `message` in detail
- ✅ Map `OperationStatus` consistently
- ❌ Never return 200 OK with error in body
- ❌ Never expose internal exception details

---

## Platform Error Response Pattern

**Decision**: Platform integrations return user-friendly messages.

**Implementation**:
```python
# infrastructure/commands/providers/slack.py
from infrastructure.commands.responses import ErrorMessage, SlackResponseFormatter

@register_command_provider("slack")
class SlackCommandProvider(CommandProvider):
    def handle(self, platform_payload: Dict[str, Any]) -> None:
        # Acknowledge immediately
        self.acknowledge(platform_payload)
        
        # Process command
        result = add_member_to_group(request)
        
        # ✅ Format error for Slack users
        if not result.is_success:
            error = ErrorMessage(
                error_code=result.error_code or "ERROR",
                message=self._make_user_friendly_message(result),
                details=None  # Don't expose internals to users
            )
            
            # ✅ Platform formatter adds emojis and formatting
            formatted = self.formatter.format_error(error)
            self.respond(formatted)
            return
        
        # ✅ Success message with emoji
        self.respond(f":white_check_mark: {result.data['member_email']} added to {result.data['group_name']}")
    
    def _make_user_friendly_message(self, result: OperationResult) -> str:
        """Convert technical errors to user-friendly messages."""
        if result.status == OperationStatus.NOT_FOUND:
            return "I couldn't find that group. Please check the name and try again."
        elif result.status == OperationStatus.UNAUTHORIZED:
            return "You don't have permission to do that. Please contact your administrator."
        elif result.status == OperationStatus.PERMANENT_ERROR:
            return f"There was a problem: {result.message}"
        else:  # TRANSIENT_ERROR
            return "The service is temporarily unavailable. Please try again in a few minutes."
```

**Platform Response Examples**:

**Slack Block Kit**:
```json
{
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": ":x: *GROUP_NOT_FOUND*\nI couldn't find that group. Please check the name and try again."
      }
    }
  ]
}
```

**Teams Adaptive Card**:
```json
{
  "type": "AdaptiveCard",
  "version": "1.4",
  "body": [
    {
      "type": "TextBlock",
      "text": "❌ Error",
      "weight": "Bolder",
      "color": "Attention"
    },
    {
      "type": "TextBlock",
      "text": "I couldn't find that group. Please check the name and try again.",
      "wrap": true
    }
  ]
}
```

**Rules**:
- ✅ Use conversational language for chat platforms
- ✅ Include emojis for visual feedback (`:x:`, `:white_check_mark:`)
- ✅ Hide technical error codes from users (log them internally)
- ✅ Provide actionable guidance ("Please contact your administrator")
- ❌ Never show stack traces or internal errors in chat
- ❌ Never use HTTP status codes in chat messages

---

## 5.3 Unified Error Logging

**Decision**: Log all errors with structured context, regardless of interface.

**Implementation**:
```python
import structlog

logger = structlog.get_logger()

def add_member_to_group(request: AddMemberRequest) -> OperationResult:
    """Business logic logs errors consistently."""
    log = logger.bind(
        group_id=request.group_id,
        member_email=request.member_email
    )
    
    try:
        # ... business logic ...
        log.info("member_added_successfully")
        return OperationResult.success(data={"member_email": request.member_email})
    
    except Exception as e:
        # ✅ Log with full context for both API and platform calls
        log.error(
            "member_add_failed",
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True  # Include stack trace in logs
        )
        
        # Return OperationResult (caller decides how to format for user)
        return OperationResult.permanent_error(
            message="Failed to add member",
            error_code="MEMBER_ADD_FAILED"
        )
```

**Audit Log Example**:
```json
{
  "event": "member_add_failed",
  "timestamp": "2026-01-13T10:30:45Z",
  "group_id": "eng-team",
  "member_email": "user@example.com",
  "operation": "add_member",
  "error_type": "PermissionError",
  "error_message": "Insufficient permissions",
  "user_id": "slack:T123:U456",
  "source": "slack",
  "correlation_id": "abc-123-def-456"
}
```

**Rules**:
- ✅ Log all errors with structured context
- ✅ Include `correlation_id` for tracing across services
- ✅ Log `user_id` and `source` (slack, api, teams)
- ✅ Include stack traces in logs (not in user responses)
- ❌ Never log sensitive data (tokens, passwords)
- ❌ Never suppress error logs
