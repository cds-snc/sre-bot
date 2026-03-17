# Operation Result Pattern

## Status

**ACCEPTED** - February 2026

## Context

The SRE Bot integrates with multiple third-party services (Google Workspace, AWS Identity Center, etc.) that handle API calls and responses in different ways:

- **Google API**: Raises `googleapiclient.errors.HttpError` with HTTP status codes
- **AWS SDK**: Raises `botocore.exceptions.ClientError` with error code strings  
- **Other services**: Each with their own error conventions

This heterogeneity creates challenges:

1. **Inconsistent error handling** across providers
2. **Code duplication** in error classification logic
3. **Difficult retry logic** - which errors are transient vs permanent?
4. **Poor observability** - hard to track errors by provider/operation

Additionally, Python's exception-based error handling has limitations:
- Implicit control flow (hard to trace)
- Type checkers struggle with exception types
- Forces try/except blocks throughout the codebase

## Decision

We implement the **Result Type pattern** (inspired by Railway-Oriented Programming) to provide uniform error handling across third-party API integrations.

**Important Caveat**: This pattern is used **selectively at integration boundaries only**, not throughout the entire application. See Scott Wlaschin's ["Against Railway-Oriented Programming"](https://fsharpforfunandprofit.com/posts/against-railway-oriented-programming/) for anti-patterns to avoid.

### Core Components

1. **OperationStatus** - Enum classifying operation outcomes
2. **OperationResult** - Dataclass wrapping result or error
3. **Error Classifiers** - Provider-specific exception → OperationResult converters

```python
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

# Success case
result = OperationResult.success(
    data={"members": [...]},
    provider="google",
    operation="list_members"
)

# Error case  
result = OperationResult.error(
    status=OperationStatus.TRANSIENT_ERROR,
    message="Google API rate limited",
    error_code="RATE_LIMITED",
    retry_after=60,
    provider="google"
)

# Usage
if result.is_success:
    process(result.data)
else:
    if result.status == OperationStatus.TRANSIENT_ERROR:
        # Retry logic
    else:
        # Permanent failure
```

### Error Classification

**OperationStatus values:**

- `SUCCESS` - Operation completed successfully
- `TRANSIENT_ERROR` - Retryable (rate limit, timeout, 5xx)
- `PERMANENT_ERROR` - Non-retryable (validation, auth, 404)
- `UNAUTHORIZED` - Authentication/authorization failure
- `NOT_FOUND` - Resource not found

**Classifiers** convert provider exceptions:

```python
from infrastructure.operations.classifiers import classify_http_error

try:
    result = service.members().list(groupKey=group_id).execute()
except Exception as exc:
    return classify_http_error(exc)  # → OperationResult
```

### Functional Composition

The pattern enables functional-style error handling via Railway-Oriented Programming:

```python
# Chain operations with automatic error propagation
result = (
    fetch_user(user_id)
    .bind(validate_user)
    .bind(enrich_profile)
    .map(format_response)
)

# Only succeeds if all steps succeed
# Errors short-circuit the chain
```

**Helper methods:**

- `map(fn)` - Transform success value
- `bind(fn)` - Chain operations returning OperationResult
- `unwrap_or(default)` - Get value or default
- `unwrap()` - Get value or raise exception

## Industry Precedent

This pattern is **standard practice** in modern software development:

### Language Standard Libraries
- **Rust**: `Result<T, E>` (stdlib)
- **Kotlin**: `Result<T>` (stdlib)  
- **Swift**: `Result<Success, Failure>` (stdlib)
- **OCaml**: `type ('a, 'b) result` (stdlib)
- **Haskell**: `Either a b` (by convention)

### Python Community
- **dry-python/returns** (4.2k stars) - Comprehensive FP library
- **rustedpy/result** (1.7k stars) - Rust-inspired Result type

### Pattern Recognition
- **Railway-Oriented Programming** - F# community
- **12-Factor Apps** - Factor IV (Backing Services)
- **Enterprise Integration Patterns** - Uniform interface

## Consequences

### Positive

✅ **Uniform interface** - All providers return OperationResult  
✅ **Explicit errors** - No hidden exceptions  
✅ **Type safety** - Better IDE/mypy support  
✅ **Retry logic** - Encoded in OperationStatus  
✅ **Observability** - Provider/operation tracking  
✅ **Vertical isolation** - Modules/packages are provider-agnostic  
✅ **Testability** - Easy to mock results  
✅ **Functional composition** - Chain operations elegantly  

### Negative

⚠️ **Learning curve** - Team must understand the pattern  
⚠️ **Verbosity** - More code than raw exceptions (but clearer)  
⚠️ **Custom pattern** - Not using stdlib (but Python has no Result type)  
⚠️ **I/O complexity** - Must carefully decide what deserves Result vs exception

### Neutral

🔵 **Different from "Pythonic"** - Exceptions are idiomatic, but this is better for our use case  
🔵 **Not FastAPI built-in** - HTTPException only works at HTTP layer  

## Addressing "Against Railway-Oriented Programming"

Scott Wlaschin (who coined the ROP term) warns against overuse. We've assessed our usage against his 8 warnings:

### ✅ **Appropriate Use (Passed Checks)**

1. **No diagnostics in Result** - We don't store stack traces or exceptions in Result
2. **Not reinventing try/catch** - We convert exceptions to Results only at integration boundaries
3. **Results are visible** - Business logic receives and acts on Results
4. **Error cases matter** - Transient vs permanent distinction is critical for retry logic
5. **Not a performance concern** - API calls are already slow; Result overhead is negligible
6. **Simple interop** - FastAPI endpoints convert Results to HTTP responses at boundary

### ⚠️ **Requires Vigilance**

**7. Fail fast when appropriate** - We should use exceptions (not Results) for:
- Configuration file not found at startup
- Missing required environment variables
- Database connection completely unavailable
- **Rule**: If the app cannot continue, throw exception immediately

**8. I/O Error Modeling** - Scott warns: *"Don't try to model every possible I/O error with a Result"*

Our justification:
- ✅ We model **only 5 statuses** (not every API error code)
- ✅ Categories are **minimal and domain-relevant**: Can we retry? Is resource missing?
- ✅ Provider abstraction **is our domain** - uniform handling is a business requirement
- ⚠️ **Scope limited to integration layer** - Not used for internal logic

### **The Key Test: Domain vs Infrastructure**

Scott's error classification:
- **Domain Errors** → Use Result (expected business failures)
- **Infrastructure Errors** → Case-by-case (ask domain experts)
- **Panics** → Use exceptions (unexpected failures)

**Our determination:**
- Rate limiting, throttling, network timeouts → **Domain concerns** for a multi-provider integration system
- The distinction between "can retry" vs "cannot retry" is a **business requirement** for reliability
- Provider errors must be **uniform** so business logic is provider-agnostic

Therefore, our use of Result for API integration errors is appropriate **because integration IS our domain**.

### **Where We DON'T Use Result**

Examples of appropriate exception usage in our codebase:
- Application startup failures (fail fast)
- Missing configuration (panic)
- Internal business logic errors (local exceptions)
- Validation errors within a single function (raise and catch locally)

### **Boundary Rule**

**Use Result**: At integration boundaries (Google API, AWS SDK, external APIs)  
**Use Exceptions**: Everywhere else unless retry logic is needed at call site  

## Alternatives Considered

### 1. Raw Exceptions
**Rejected**: Implicit control flow, poor type safety, duplication

### 2. Tuple Returns `(value, error)`
**Rejected**: No type safety, confusing semantics (`None, None`?)

### 3. Third-party Libraries (dry-python/returns)
**Rejected**: Heavy dependency, not tailored to our needs, overkill

### 4. HTTPException Everywhere
**Rejected**: Only works at HTTP layer, not for business logic

## Implementation

**Location:**
- `infrastructure/operations/status.py` - OperationStatus enum
- `infrastructure/operations/result.py` - OperationResult dataclass  
- `infrastructure/operations/classifiers.py` - Error classifiers
- `tests/unit/infrastructure/test_operations_result.py` - Comprehensive tests with usage examples

**Usage:**
```python
from infrastructure.operations.classifiers import classify_http_error
from infrastructure.operations.result import OperationResult

def list_group_members(group_id: str) -> OperationResult:
    try:
        response = service.members().list(groupKey=group_id).execute()
        return OperationResult.success(
            data=response.get('members', []),
            provider='google',
            operation='list_members'
        )
    except Exception as exc:
        return classify_http_error(exc)
```

**Railway-Oriented Programming:**
```python
# Chain operations with automatic error propagation
result = (
    OperationResult.success(data=user_id)
    .bind(validate_user)
    .bind(fetch_from_database)
    .bind(enrich_profile)
    .map(format_response)
)
# Errors short-circuit the chain automatically
```

See `tests/unit/infrastructure/test_operations_result.py` for comprehensive examples.

## References

- [Railway-Oriented Programming (F#)](https://fsharpforfunandprofit.com/rop/)
- **[Against Railway-Oriented Programming](https://fsharpforfunandprofit.com/posts/against-railway-oriented-programming/)** - When NOT to use it
- [Rust Result Type](https://doc.rust-lang.org/std/result/)
- [dry-python/returns](https://github.com/dry-python/returns)
- [12-Factor Apps - Backing Services](https://12factor.net/backing-services)
- [Wikipedia - Result Type](https://en.wikipedia.org/wiki/Result_type)
- [Microsoft F# Error Management](https://learn.microsoft.com/en-us/dotnet/fsharp/language-reference/results)

## Notes

This pattern is being used in production by major languages and frameworks. It's not over-engineering - it's applying proven solutions to real problems.

The pattern provides the **type-safe error handling** and **uniform interfaces** needed for a multi-provider integration system, while enabling clean vertical feature isolation in our modular architecture.
