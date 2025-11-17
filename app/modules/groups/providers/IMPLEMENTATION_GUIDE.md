# Group Provider Implementation Guide

This guide provides step-by-step instructions for implementing a new group provider that extends the provider contract defined in the SRE Bot's group management module.

## Quick Start

1. Create a new Python class extending `GroupProvider` or `PrimaryGroupProvider`
2. Implement all abstract methods (see [Required Methods](#required-methods))
3. Implement the `classify_error()` method to handle provider-specific errors
4. Implement the `_health_check_impl()` method for lightweight connectivity checks
5. Register your provider using the `@register_provider()` decorator
6. Configure your provider in `settings.groups.providers.*`

---

## Architecture Overview

The provider framework uses a **contract-based design pattern** with the following key concepts:

- **contracts.py**: Pure data structures (`OperationResult`, `HealthCheckResult`, `ProviderCapabilities`, `CircuitBreakerStats`)
- **base.py**: Abstract classes (`GroupProvider`, `PrimaryGroupProvider`) and operation lifecycle
- **GroupProvider (ABC)**: Base abstract class defining the core provider contract
- **PrimaryGroupProvider (ABC)**: Extends GroupProvider with permission validation and manager checks
- **Email-Based Operations**: Write operations accept `member_email: str` as the universal identifier
- **OperationResult**: Uniform response type for all provider operations
- **Circuit Breaker**: Built-in protection against cascading failures (public methods wrap `_*_impl` methods)
- **Email Validation**: Centralized RFC-compliant validation via `validate_member_email()`

### Email-Based Member Operations

Provider write operations use email addresses as the universal member identifier. The public methods (`add_member`, `remove_member`) wrap the implementation methods (`_add_member_impl`, `_remove_member_impl`) with circuit breaker protection:

```python
# Public interface with circuit breaker protection
def add_member(self, group_key: str, member_email: str) -> OperationResult:
    """Add member to group by email address (circuit breaker protected)."""
    if self._circuit_breaker:
        return self._circuit_breaker.call(
            self._add_member_impl, group_key, member_email
        )
    else:
        return self._add_member_impl(group_key, member_email)

# Implementation method (use @provider_operation decorator for error handling)
@provider_operation(data_key="result")
def _add_member_impl(self, group_key: str, member_email: str) -> dict:
    """Implementation - returns dict, not OperationResult."""
    validated_email = validate_member_email(member_email)
    internal_user_id = self._resolve_email_to_id(validated_email)
    result = self.api.add_member(group_key, internal_user_id)
    return {"status": "added", "email": validated_email}
```

Benefits of email-based operations:
- Consistent interface across all providers
- Better encapsulation (providers handle their own ID resolution)
- Type safety with string parameters
- Email validation at provider layer
- Circuit breaker protection handled automatically by the framework

## Provider Registration

### Basic Registration

Use the `@register_provider()` decorator to register your provider class:

```python
from modules.groups.providers import register_provider
from modules.groups.providers.base import GroupProvider

@register_provider("my_provider")
class MyProvider(GroupProvider):
    """Custom group provider implementation."""
    pass
```

The provider name ("my_provider") is used during configuration and activation.

### Activation Flow

Providers follow a two-stage lifecycle:

**Stage 1: Discovery** (at module import time)
- `@register_provider()` decorator records provider classes in `DISCOVERED_PROVIDER_CLASSES`
- No instantiation occurs
- Framework builds a registry of available provider classes

**Stage 2: Activation** (when `load_providers()` or `activate_providers()` is called)
1. Reads `settings.groups.providers` configuration once
2. Filters out disabled providers
3. Instantiates remaining providers using fallback strategies:
   - Calls no-arg `__init__()`
   - Falls back to no-arg classmethod `from_config()` or `from_empty_config()`
4. Applies configuration domain overrides (API keys, etc.)
5. Resolves and sets provider prefix
6. Applies capability overrides from config
7. Validates prefix uniqueness across all active providers
8. Determines primary provider using priority rules
9. Populates `PROVIDER_REGISTRY` with instantiated providers

Returns the primary provider name for validation.

### Prefix Management

Providers can be assigned a prefix that's used for composing/parsing group names:

```python
# In provider class
@property
def prefix(self) -> str:
    """Default prefix (can be overridden by config)."""
    return self.__class__.__name__.lower()

# Access prefix on instance
prefix = provider_instance.prefix  # Returns configured or default prefix
mapping_prefix = provider_instance.get_mapping_prefix()  # None for primary, prefix for secondaries
```

## Required Methods

All providers must implement the following abstract methods from the base class.

### Core Methods (GroupProvider)

```python
@property
def capabilities(self) -> ProviderCapabilities:
    """Return provider capability descriptor.
    
    Must return a ProviderCapabilities instance indicating:
    - is_primary: Is this the canonical/primary provider?
    - supports_member_management: Can add/remove members? (default: True)
    - provides_role_info: Does API return member roles?
    - supports_user_creation: Can create users?
    - supports_user_deletion: Can delete users?
    - And other capability flags
    
    Example:
        return ProviderCapabilities(
            is_primary=True,
            supports_member_management=True,
            provides_role_info=True,
            supports_user_creation=False,
        )
    """
    pass

@provider_operation(data_key="result")
def _add_member_impl(
    self, group_key: str, member_email: str
) -> dict:
    """Add a member to a group by email.
    
    The @provider_operation decorator wraps this method to:
    - Catch exceptions and classify them via classify_error()
    - Wrap dict results in OperationResult
    - Nest results under the specified data_key
    - Avoid double-wrapping if you return OperationResult directly

    Args:
        group_key: Identifier for the group in this provider
        member_email: Email address of the member to add
    
    Returns:
        Dict with member details (will be wrapped by decorator as {"result": {...}})
    
    Raises:
        ValueError: For invalid email format (classified as PERMANENT_ERROR)
        TimeoutError: For transient network issues (classified as TRANSIENT_ERROR)
    """
    pass

@provider_operation(data_key="result")
def _remove_member_impl(
    self, group_key: str, member_email: str
) -> dict:
    """Remove a member from a group by email.
    
    The @provider_operation decorator wraps this method to:
    - Catch exceptions and classify them via classify_error()
    - Wrap dict results in OperationResult
    - Nest results under the specified data_key
    - Avoid double-wrapping if you return OperationResult directly

    Args:
        group_key: Identifier for the group in this provider
        member_email: Email address of the member to remove
    
    Returns:
        Dict with operation status (will be wrapped by decorator as {"result": {...}})
    
    Raises:
        ValueError: For invalid email format (classified as PERMANENT_ERROR)
        TimeoutError: For transient network issues (classified as TRANSIENT_ERROR)
    """
    pass

@provider_operation(data_key="members")
def _get_group_members_impl(
    self, group_key: str, **kwargs
) -> list:
    """Return list of members in a group.
    
    The @provider_operation decorator wraps list results as {"members": [...]}
    """
    pass

@provider_operation(data_key="groups")
def _list_groups_impl(self, **kwargs) -> list:
    """Return list of groups from the provider.
    
    The @provider_operation decorator wraps list results as {"groups": [...]}
    """
    pass

@provider_operation(data_key="groups")
def _list_groups_with_members_impl(self, **kwargs) -> list:
    """Return list of groups with their members.
    
    The @provider_operation decorator wraps list results as {"groups": [...]}
    """
    pass

@provider_operation(data_key="health")
def _health_check_impl(self) -> dict:
    """Lightweight health check for provider connectivity.
    
    Should perform minimal API call to verify the provider is:
    - Accessible and responsive
    - Properly authenticated
    - Able to perform basic operations
    
    Example: Authenticate and get org info, or list 1 group
    Should NOT list all groups (too expensive).
    
    The @provider_operation decorator wraps the result as {"health": {...}}
    
    Returns:
        Dict with 'status' and optional 'message' fields
        Possible statuses: 'healthy', 'degraded', 'unhealthy'
    """
    pass

def classify_error(self, exc: Exception) -> OperationResult:
    """Classify provider-specific exceptions into OperationResult.
    
    Called by @provider_operation decorator to handle exceptions from
    _*_impl methods with intelligent error classification.
    
    Categorize provider API errors to standard error types:
    - Rate limits (429) → TRANSIENT_ERROR with retry_after
    - Auth errors (401/403) → PERMANENT_ERROR
    - Not found (404) → PERMANENT_ERROR (usually means bad group_key)
    - Server errors (5xx) → TRANSIENT_ERROR
    - Timeouts/connection → TRANSIENT_ERROR
    - Invalid email format → PERMANENT_ERROR
    - Unexpected errors → TRANSIENT_ERROR (default)
    
    Args:
        exc: Exception raised by provider operation
    
    Returns:
        OperationResult with appropriate status, error_code, and retry_after
    
    Example:
        def classify_error(self, exc: Exception) -> OperationResult:
            if isinstance(exc, RateLimitError):
                return OperationResult.transient_error(
                    message=str(exc),
                    error_code="RATE_LIMITED",
                    retry_after=exc.retry_after_seconds,
                )
            elif isinstance(exc, AuthError):
                return OperationResult.permanent_error(
                    message=str(exc),
                    error_code="AUTH_FAILED",
                )
            else:
                return OperationResult.transient_error(str(exc))
    """
    pass
```

### Primary Provider Methods (PrimaryGroupProvider only)

If extending `PrimaryGroupProvider`, also implement:

```python
@provider_operation(data_key="permission")
def _validate_permissions_impl(
    self, user_key: str, group_key: str, action: str
) -> dict:
    """Validate if user has permission for action on group.
    
    The @provider_operation decorator wraps the result as {"permission": {...}}
    """
    pass

@provider_operation(data_key="result")
def _is_manager_impl(
    self, user_key: str, group_key: str
) -> dict:
    """Check if user is a manager of the group.
    
    The @provider_operation decorator wraps the result as {"result": {...}}
    """
    pass
```

Note: `_list_groups_for_user_impl` and `_list_groups_managed_by_user_impl` are not part of the base contract.
Providers that support user-specific group queries should implement them as needed.

## Key Design Patterns

### 1. The `_impl` Pattern: Public Methods with Circuit Breaker + Private `_*_impl` Methods

All public methods have built-in circuit breaker protection. Providers implement private `_*_impl` methods decorated with `@provider_operation`:

```python
# Framework's public method (circuit breaker wrapped)
class GroupProvider:
    def add_member(self, group_key: str, member_email: str) -> OperationResult:
        """Public method with circuit breaker protection (framework provided)."""
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(
                    self._add_member_impl, group_key, member_email
                )
            except CircuitBreakerOpenError as e:
                logger.warning("circuit_breaker_rejected_add_member", ...)
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._add_member_impl(group_key, member_email)

# Provider's implementation method (with @provider_operation decorator)
@provider_operation(data_key="result")
def _add_member_impl(self, group_key: str, member_email: str) -> dict:
    """Implementation with automatic error classification and response wrapping.
    
    The @provider_operation decorator:
    1. Catches exceptions and calls classify_error(exc)
    2. Wraps dict results in OperationResult
    3. Avoids double-wrapping if you return OperationResult directly
    4. Nests results under the data_key ("result" in this case)
    """
    validated_email = validate_member_email(member_email)
    resp = self.api.add_member(group_key, validated_email)
    return {"status": "added", "email": validated_email}
```

The separation of concerns:
- **Public method** (framework-provided): Handles circuit breaker logic
- **Private `_*_impl` method** (provider-implemented): Contains business logic, decorated with `@provider_operation`
- **`@provider_operation` decorator**: Handles error classification and response wrapping

The decorator automatically handles:
- Exception catching and classification via `self.classify_error(exc)`
- Response wrapping in `OperationResult`
- Nesting results under `data_key` for consistent response structure
- Pass-through of direct `OperationResult` returns to avoid double-wrapping

### 2. Email Validation and Error Classification

Email validation happens at the provider layer for all write operations:

```python
from modules.groups.providers.base import validate_member_email

@provider_operation(data_key="result")
def _add_member_impl(self, group_key: str, member_email: str) -> dict:
    """Email is validated and normalized by validate_member_email()."""
    try:
        validated_email = validate_member_email(member_email)
    except ValueError as e:
        # @provider_operation decorator will catch and classify this
        raise ValueError(f"Invalid email: {e}")
    
    # Resolve email to internal user ID (provider-specific)
    user_id = self._resolve_email_to_id(validated_email)
    
    # Perform the operation
    resp = self.api.add_member(group_key, user_id)
    return {"status": "added", "email": validated_email}
```

Error classification determines retry behavior:

```python
def classify_error(self, exc: Exception) -> OperationResult:
    """Classify exceptions for intelligent retry logic."""
    # TRANSIENT_ERROR: Framework will retry
    if isinstance(exc, TimeoutError):
        return OperationResult.error(
            status=OperationStatus.TRANSIENT_ERROR,
            message="Timeout",
            error_code="TIMEOUT",
        )
    
    # PERMANENT_ERROR: Framework will NOT retry
    if isinstance(exc, ValueError):  # Invalid email
        return OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message=str(exc),
            error_code="INVALID_INPUT",
        )
    
    # Default: treat as transient
    return OperationResult.error(
        status=OperationStatus.TRANSIENT_ERROR,
        message=str(exc),
    )
```

### 3. Email-to-ID Resolution

Each provider handles its own email → ID resolution internally:

```python
@provider_operation(data_key="result")
def _add_member_impl(self, group_key: str, member_email: str) -> dict:
    """Provider resolves email to internal ID representation."""
    # Validate email format
    validated_email = validate_member_email(member_email)
    
    # Provider-specific email → ID resolution
    # Each provider knows how to map emails to their internal IDs
    user_id = self._resolve_email_to_user_id(validated_email)
    
    # Perform group membership operation using internal ID
    resp = self.api.add_group_member(group_key, user_id)
    
    # Return canonical member dict (will be wrapped by @provider_operation)
    return {
        "email": validated_email,
        "id": user_id,
        "role": "member",
    }
```

This approach provides clear separation of concerns: orchestration passes emails, providers handle internal ID resolution.

### 4. Using the @provider_operation Decorator

The `@provider_operation` decorator wraps methods with error handling and response construction:

```python
from modules.groups.providers.base import provider_operation

@provider_operation(data_key="members")
def _get_group_members_impl(self, group_key: str, **kwargs) -> list:
    """The @provider_operation decorator automatically:
    1. Catches exceptions from _*_impl methods
    2. Classifies exceptions via self.classify_error(exc)
    3. Wraps successful dict/list results in OperationResult
    4. Nests results under the specified data_key
    5. Avoids double-wrapping if you return OperationResult directly
    
    Args:
        group_key: Provider group identifier
        **kwargs: Additional provider parameters
    
    Returns:
        List of member dicts (will be nested under data_key="members")
    """
    resp = self.api.list_members(group_key)
    return [self._normalize_member_from_provider(m) for m in resp]
```

The decorator handles the entire request/response cycle:

```python
# How @provider_operation works internally:
from modules.groups.providers.base import provider_operation, OperationResult

def provider_operation(data_key=None):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            try:
                result = func(self, *args, **kwargs)
                # If provider returned OperationResult, pass through unchanged
                if isinstance(result, OperationResult):
                    return result
                # Otherwise wrap the result under data_key
                data = {data_key: result} if data_key else result
                return OperationResult(
                    status=OperationStatus.SUCCESS,
                    message="ok",
                    data=data
                )
            except Exception as e:
                # Use provider's error classification
                return self.classify_error(e)
        return wrapper
    return decorator
```

Benefits of using the decorator:
- Your `_*_impl` methods only need to return dicts or lists
- Exceptions are automatically classified via `classify_error()`
- Response structure is consistent across all providers
- No need to manually construct `OperationResult` objects in implementation code

## Configuration and Customization

### Configuration Structure

Providers are configured in `settings.groups.providers.*`:

```yaml
groups:
  circuit_breaker_enabled: true
  circuit_breaker_failure_threshold: 5
  circuit_breaker_timeout_seconds: 60
  circuit_breaker_half_open_max_calls: 3
  providers:
    google_workspace:
      enabled: true
      domain: example.com
      api_key: "..."
      is_primary: true
      provides_role_info: true
    aws_identity_center:
      enabled: true
      api_key: "..."
      prefix: "aws"
```

### Accessing Configuration in Providers

**Providers should NOT access config directly in `__init__()`** to support testing and instantiation without global config. Instead, use:

```python
class MyProvider(GroupProvider):
    def __init__(self):
        """No-arg constructor that sets sensible defaults."""
        super().__init__()  # Initialize circuit breaker with defaults
        self.api_key = None
        self.domain = None
    
    @classmethod
    def from_config(cls):
        """Optional: classmethod to instantiate from global config."""
        from core.config import settings
        instance = cls()
        cfg = settings.groups.providers.get("my_provider", {})
        instance.api_key = cfg.get("api_key")
        instance.domain = cfg.get("domain")
        return instance
```

The activation system (`registry_utils.py`) applies configuration using the strategy:
1. Tries `from_config()` if it exists
2. Falls back to no-arg `__init__()`
3. Applies domain and capability overrides automatically

## Testing Your Provider

When testing, mock the API and verify error classification:

```python
import pytest
from modules.groups.providers.base import OperationStatus

def test_provider_handles_rate_limit():
    """Verify provider correctly classifies rate limit errors."""
    provider = ExampleProvider()
    provider.api = Mock()
    provider.api.add_member.side_effect = ExampleRateLimitError(retry_after=30)
    
    result = provider.add_member("group1", "user@example.com")
    
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "RATE_LIMITED"
    assert result.retry_after == 30

def test_provider_handles_auth_error():
    """Verify auth errors are permanent (not retried)."""
    provider = ExampleProvider()
    provider.api = Mock()
    provider.api.add_member.side_effect = ExampleAuthError()
    
    result = provider.add_member("group1", "user@example.com")
    
    assert result.status == OperationStatus.PERMANENT_ERROR
    assert result.error_code == "AUTH_FAILED"

def test_provider_validates_email():
    """Verify invalid emails are rejected."""
    provider = ExampleProvider()
    
    result = provider.add_member("group1", "invalid-email")
    
    assert result.status == OperationStatus.PERMANENT_ERROR
    assert result.error_code == "INVALID_INPUT"
```

## Example: Minimal Provider Implementation

```python
from modules.groups.providers import register_provider
from modules.groups.providers.base import (
    GroupProvider,
    ProviderCapabilities,
    OperationResult,
    OperationStatus,
    provider_operation,
    validate_member_email,
)

@register_provider("example")
class ExampleProvider(GroupProvider):
    """Minimal example provider implementation."""
    
    def __init__(self):
        """Initialize with sensible defaults."""
        super().__init__()  # Creates circuit breaker
        self.api = None  # Set by from_config() or manually
    
    @classmethod
    def from_config(cls):
        """Instantiate from global config (optional)."""
        from core.config import settings
        instance = cls()
        cfg = settings.groups.providers.get("example", {})
        instance.api = ExampleAPI(cfg.get("api_key"))
        return instance
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        """Define what this provider can do."""
        return ProviderCapabilities(
            is_primary=False,
            supports_member_management=True,
            provides_role_info=True,
            supports_user_creation=False,
        )
    
    def classify_error(self, exc: Exception) -> OperationResult:
        """Classify provider-specific errors for retry logic."""
        if isinstance(exc, ExampleRateLimitError):
            return OperationResult.transient_error(
                message=f"Rate limited: {exc}",
                error_code="RATE_LIMITED",
                retry_after=exc.retry_after,
            )
        elif isinstance(exc, ExampleAuthError):
            return OperationResult.permanent_error(
                message=f"Auth failed: {exc}",
                error_code="AUTH_FAILED",
            )
        elif isinstance(exc, ValueError):
            # Invalid email, invalid input, etc.
            return OperationResult.permanent_error(
                message=str(exc),
                error_code="INVALID_INPUT",
            )
        else:
            # Default: treat as transient
            return OperationResult.transient_error(str(exc))
    
    @provider_operation(data_key="result")
    def _add_member_impl(self, group_key: str, member_email: str) -> dict:
        """Add member to group by email."""
        validated_email = validate_member_email(member_email)
        user_id = self.api.resolve_email_to_id(validated_email)
        result = self.api.add_member(group_key, user_id)
        return {
            "status": "added",
            "email": validated_email,
            "member": validated_email,
        }
    
        @provider_operation(data_key="result")
    def _remove_member_impl(self, group_key: str, member_email: str) -> dict:
        """Remove member from group by email."""
        validated_email = validate_member_email(member_email)
        user_id = self.api.resolve_email_to_id(validated_email)
        self.api.remove_member(group_key, user_id)
        return {"status": "removed", "email": validated_email}
    
    @provider_operation(data_key="members")
    def _get_group_members_impl(self, group_key: str, **kwargs) -> list:
        """Get members of a group."""
        members = self.api.list_members(group_key)
        return [
            {
                "email": m["email"],
                "id": m["id"],
                "role": m.get("role", "MEMBER"),
            }
            for m in members
        ]
    
    @provider_operation(data_key="groups")
    def _list_groups_impl(self, **kwargs) -> list:
        """List all groups."""
        groups = self.api.list_groups()
        return [
            {
                "id": g["id"],
                "name": g["name"],
                "email": g["email"],
            }
            for g in groups
        ]
    
    @provider_operation(data_key="groups")
    def _list_groups_with_members_impl(self, **kwargs) -> list:
        """List groups with members (optional optimization)."""
        groups = self.api.list_groups()
        return [
            {
                "id": g["id"],
                "name": g["name"],
                "email": g["email"],
                "members": self._get_group_members_impl(g["id"]).data["members"],
            }
            for g in groups
        ]
    
    @provider_operation(data_key="health")
    def _health_check_impl(self) -> dict:
        """Lightweight health check (minimal API call)."""
        try:
            org_info = self.api.get_org_info()
            return {"status": "healthy", "org": org_info}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
```

## Testing Your Provider

When testing, mock the API and verify error classification:

```python
import pytest
from modules.groups.providers.base import OperationStatus

def test_provider_handles_rate_limit():
    """Verify provider correctly classifies rate limit errors."""
    provider = ExampleProvider()
    provider.api = Mock()
    provider.api.add_member.side_effect = ExampleRateLimitError(retry_after=30)
    
    result = provider.add_member("group1", "user@example.com")
    
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "RATE_LIMITED"
    assert result.retry_after == 30

def test_provider_handles_auth_error():
    """Verify auth errors are permanent (not retried)."""
    provider = ExampleProvider()
    provider.api = Mock()
    provider.api.add_member.side_effect = ExampleAuthError()
    
    result = provider.add_member("group1", "user@example.com")
    
    assert result.status == OperationStatus.PERMANENT_ERROR
    assert result.error_code == "AUTH_FAILED"

def test_provider_validates_email():
    """Verify invalid emails are rejected."""
    provider = ExampleProvider()
    
    result = provider.add_member("group1", "invalid-email")
    
    assert result.status == OperationStatus.PERMANENT_ERROR
    assert result.error_code == "INVALID_INPUT"
```

## Migration Guide

### From Legacy Provider Implementations

If migrating from a legacy provider implementation:

1. **Update method signatures** to use email-based operations:
   ```python
   # Before (Legacy) - took NormalizedMember objects
   def _add_member_impl(self, group_key: str, member_data: NormalizedMember) -> OperationResult:
   
   # After (Current) - takes email strings
   @provider_operation(data_key="result")
   def _add_member_impl(self, group_key: str, member_email: str) -> dict:
   ```

2. **Return dicts instead of OperationResult** from `_*_impl` methods:
   ```python
   # Before
   return OperationResult(status=OperationStatus.SUCCESS, data={...})
   
   # After
   return {"status": "added", "email": validated_email}  # Wrapped by decorator
   ```

3. **Add @provider_operation decorator** to all `_*_impl` methods:
   ```python
   from modules.groups.providers.base import provider_operation
   
   @provider_operation(data_key="result")  # Matches what you're returning
   def _add_member_impl(self, group_key: str, member_email: str) -> dict:
       return {...}
   ```

4. **Add email validation** in write operations:
   ```python
   from modules.groups.providers.base import validate_member_email
   
   validated_email = validate_member_email(member_email)
   user_id = self._resolve_email_to_user_id(validated_email)
   ```

5. **Implement classify_error()** to categorize exceptions:
   ```python
   def classify_error(self, exc: Exception) -> OperationResult:
       if isinstance(exc, RateLimitError):
           return OperationResult.transient_error(..., retry_after=...)
       elif isinstance(exc, AuthError):
           return OperationResult.permanent_error(...)
       else:
           return OperationResult.transient_error(str(exc))
   ```

### Backward Compatibility

The current provider framework is **NOT backward compatible** with legacy implementations that use `NormalizedMember` objects or return `OperationResult` directly from `_*_impl` methods. All providers must follow the current email-based pattern with `@provider_operation` decorators.
   def _add_member_impl(self, group_key: str, member_email: str) -> dict:
       ...
   ```

3. **Implement email validation** in write operations:
   ```python
   from modules.groups.providers.base import validate_member_email
   
   validated_email = validate_member_email(member_email)
   ```

4. **Update error classification** to work with @provider_operation:
   ```python
   def classify_error(self, exc: Exception) -> OperationResult:
       # Categorize exceptions for retry logic
       if isinstance(exc, TimeoutError):
           return OperationResult.error(
               status=OperationStatus.TRANSIENT_ERROR,
               message="Timeout"
           )
   ```

5. **Remove normalization calls** from orchestration layer.

### Backward Compatibility

The provider framework is **NOT backward compatible** with legacy provider implementations. All new code must use email-based signatures and @provider_operation decorator.

## Troubleshooting

### Provider Not Activating

Check that:
1. Provider class is registered with `@register_provider()`
2. Provider is enabled in configuration (default: enabled)
3. Provider can be instantiated with no-arg `__init__()` or has `from_config()` classmethod
4. All abstract methods are implemented

### Circuit Breaker Always Open

1. Check circuit breaker is enabled in configuration
2. Verify `classify_error()` is returning correct error statuses
3. Check failure threshold is not too low
4. Monitor error logs for systematic failures

### Tests Failing with Abstract Method Errors

1. Ensure provider implements ALL abstract methods from base class
2. Check for new abstract methods added by recent framework changes
3. Verify no typos in method names

## Performance Considerations

- **Health Checks**: Keep them lightweight (single API call, max 1 second)
- **List Operations**: Use pagination to avoid memory issues with large result sets
- **Batch Requests**: Use provider native batch APIs when available
- **Circuit Breaker**: Configure appropriately for your provider's SLA

## Additional Resources

- `providers/base.py`: Full base class documentation
- `modules/groups/models.py`: Canonical data models
- `integrations/`: Integration layer examples (Google Workspace, AWS)
