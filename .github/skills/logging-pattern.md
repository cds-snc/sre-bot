# Structured Logging Pattern

**Reference**: `copilot-instructions.md` Logging section

## Pattern

Use structlog with OpenTelemetry semantic conventions. Bind request-scoped context only.

---

## Basic Pattern

```python
import structlog

logger = structlog.get_logger()

def process_request(user_id: str, request_id: str):
    """Bind request context per-call."""
    log = logger.bind(user_id=user_id, request_id=request_id)
    log.info("request_started")
    
    # Do work
    
    log.info("request_completed", items_processed=10)
```

**Pattern**: Get logger at module level, bind context in functions.

---

## Class Pattern

```python
import structlog

class UserService:
    def __init__(self):
        self.logger = structlog.get_logger()
    
    def create_user(self, user_id: str, email: str):
        """Bind context in method."""
        log = self.logger.bind(user_id=user_id, email=email)
        log.info("user_creation_started")
        
        # Create user
        
        log.info("user_created")
```

**Pattern**: Create logger in `__init__`, bind context in methods.

---

## Phase-Based Logging

```python
# Initialization phases use phase context
log = logger.bind(phase="providers")
log.info("providers_loading")

# Load providers...

log.info("providers_loaded", count=3)
```

**Pattern**: Bind `phase` key for startup/shutdown logging.

---

## Request-Scoped Context

Bind these fields:
- `user_id`: User identifier
- `request_id`: Request correlation ID
- `customer_id`: Customer/organization ID
- `operation`: Operation name
- `service`: Service name
- `attempt`: Retry attempt number

```python
log = logger.bind(
    user_id=user_id,
    request_id=request_id,
    operation="sync_groups",
)
log.info("operation_started")
```

---

## Automatic Fields

**Never Bind These** - OpenTelemetry adds automatically:
- `code.filepath`: Source file path
- `code.function`: Function name
- `code.lineno`: Line number

```python
# ❌ FORBIDDEN
log = logger.bind(
    code_namespace="modules.groups",  # WRONG
    component="groups",  # WRONG
    module="groups",  # WRONG
)
```

**Enforcement**: Reject code that binds `code_namespace`, `component`, or `module`.

---

## Error Logging

```python
try:
    result = risky_operation()
except Exception as e:
    log.error("operation_failed", 
              error=str(e),
              error_type=type(e).__name__)
```

**Pattern**: Log `error` (message) and `error_type` (class name).

---

## Forbidden Patterns

```python
# ❌ print() statements
print("Debug info")  # WRONG - use log.debug()

# ❌ Manual code namespace
log = logger.bind(code_namespace="modules.groups")  # WRONG

# ❌ Logging secrets
log.info("token_received", token=secret_token)  # WRONG

# ❌ Reassigning logger
logger = logger.bind(...)  # WRONG - use log = logger.bind()
```

---

## Pre-Implementation Checklist

Before generating logging code:

1. ☐ Import: `import structlog`
2. ☐ Module-level: `logger = structlog.get_logger()`
3. ☐ Function-level: `log = logger.bind(...)`
4. ☐ Only bind request-scoped context (user_id, request_id, etc.)
5. ☐ Never bind code_namespace, component, or module
6. ☐ No print() statements
7. ☐ No secrets in log output
