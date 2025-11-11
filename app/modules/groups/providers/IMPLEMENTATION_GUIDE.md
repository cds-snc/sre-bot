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

- **GroupProvider (ABC)**: Base abstract class defining the core provider contract
- **PrimaryGroupProvider (ABC)**: Extends GroupProvider with additional methods for the canonical provider
- **Email-Based Operations**: Write operations accept `member_email: str` as the universal identifier
- **OperationResult**: Uniform response type for all provider operations
- **@provider_operation Decorator**: Handles error classification and response wrapping
- **Circuit Breaker**: Built-in protection against cascading failures
- **Email Validation**: Centralized RFC-compliant validation via `validate_member_email()`

### Email-Based Member Operations

Provider write operations use email addresses as the universal member identifier:

```python
# All providers implement these signatures:
def add_member(self, group_key: str, member_email: str) -> OperationResult:
    """Add member to group by email address."""

def remove_member(self, group_key: str, member_email: str) -> OperationResult:
    """Remove member from group by email address."""

# Each provider resolves email → internal ID internally
validated_email = validate_member_email(member_email)
internal_user_id = provider_api.resolve_email_to_id(validated_email)
```

Benefits of email-based operations:
- Consistent interface across all providers
- Better encapsulation (providers handle their own ID resolution)
- Type safety with string parameters
- Email validation at provider layer

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

### Activation

Providers are activated during module initialization. The `activate_providers()` function:

1. Discovers all registered provider classes
2. Filters by enabled/disabled configuration
3. Instantiates providers
4. Applies configuration overrides
5. Validates primary provider is set
6. Returns primary provider name

## Required Methods

All providers must implement the following abstract methods from the base class.

### Core Methods (GroupProvider)

```python
@property
def capabilities(self) -> ProviderCapabilities:
    """Return provider capability descriptor.
    
    Must return a ProviderCapabilities instance indicating:
    - is_primary: Is this the canonical/primary provider?
    - supports_member_management: Can add/remove members?
    - provides_role_info: Does API return member roles?
    - And other capability flags
    """
    pass

def _add_member_impl(
    self, group_key: str, member_email: str
) -> OperationResult:
    """Add a member to a group by email.
    
    The @provider_operation decorator wraps this method to:
    - Catch exceptions and classify them via classify_error()
    - Wrap dict results in OperationResult
    - Nest results under the specified data_key

    Args:
        group_key: Identifier for the group in this provider
        member_email: Email address of the member to add
    
    Returns:
        Dict with member details (will be wrapped by decorator)
    
    Raises:
        IntegrationError: For provider-specific API failures
        ValueError: For invalid email format
    """
    pass

def _remove_member_impl(
    self, group_key: str, member_email: str
) -> OperationResult:
    """Remove a member from a group by email.
    
    The @provider_operation decorator wraps this method to:
    - Catch exceptions and classify them via classify_error()
    - Wrap dict results in OperationResult
    - Nest results under the specified data_key

    Args:
        group_key: Identifier for the group in this provider
        member_email: Email address of the member to remove
    
    Returns:
        Dict with operation status (will be wrapped by decorator)
    
    Raises:
        IntegrationError: For provider-specific API failures
        ValueError: For invalid email format
    """
    pass

def _get_group_members_impl(
    self, group_key: str, **kwargs
) -> OperationResult:
    """Return list of members in a group."""
    pass

def _list_groups_impl(self, **kwargs) -> OperationResult:
    """Return list of groups from the provider."""
    pass

def _list_groups_with_members_impl(self, **kwargs) -> OperationResult:
    """Return list of groups with their members."""
    pass

def _health_check_impl(self) -> OperationResult:
    """Lightweight health check for provider connectivity.
    
    Should perform minimal API call to verify the provider is:
    - Accessible and responsive
    - Properly authenticated
    - Able to perform basic operations
    
    Example: List 1 group, or authenticate and get org info
    
    Returns:
        OperationResult with dict containing 'status' field
        Possible statuses: 'healthy', 'degraded', 'unhealthy'
    """
    pass

def classify_error(self, exc: Exception) -> OperationResult:
    """Classify provider-specific exceptions into OperationResult.
    
    Used by @provider_operation decorator to handle exceptions from
    _*_impl methods with intelligent error classification.
    
    Map provider API errors to standard error types:
    - Rate limits (429) → TRANSIENT_ERROR with retry_after
    - Auth errors (401) → PERMANENT_ERROR
    - Not found (404) → NOT_FOUND
    - Server errors (5xx) → TRANSIENT_ERROR
    - Timeouts/connection → TRANSIENT_ERROR
    
    Args:
        exc: Exception raised by provider operation
    
    Returns:
        OperationResult with appropriate status and error_code
    """
    pass
```

### Primary Provider Methods (PrimaryGroupProvider only)

If extending `PrimaryGroupProvider`, also implement:

```python
def _validate_permissions_impl(
    self, user_key: str, group_key: str, action: str
) -> OperationResult:
    """Validate if user has permission for action on group."""
    pass

def _is_manager_impl(
    self, user_key: str, group_key: str
) -> OperationResult:
    """Check if user is a manager of the group."""
    pass

def _list_groups_for_user_impl(
    self, user_key: str, provider_name: Optional[str], **kwargs
) -> OperationResult:
    """List groups that user is a member of."""
    pass

def _list_groups_managed_by_user_impl(
    self, user_key: str, provider_name: Optional[str], **kwargs
) -> OperationResult:
    """List groups that user manages."""
    pass
```

## Key Design Patterns

### 1. The `_impl` Pattern with @provider_operation Decorator

All public methods have circuit breaker protection. Providers implement private `_*_impl` methods decorated with `@provider_operation`:

```python
# Framework provides circuit breaker wrapper around public method
def add_member(self, group_key: str, member_email: str) -> OperationResult:
    """Public method with circuit breaker protection."""
    if self._circuit_breaker:
        try:
            return self._circuit_breaker.call(
                self._add_member_impl, group_key, member_email
            )
        except CircuitBreakerOpenError as e:
            return OperationResult.transient_error(...)
    else:
        return self._add_member_impl(group_key, member_email)

# Provider implements with @provider_operation decorator for error handling
@provider_operation(data_key="result")
def _add_member_impl(self, group_key: str, member_email: str) -> dict:
    """Implementation with automatic error classification and response wrapping.
    
    The @provider_operation decorator:
    1. Catches exceptions and calls classify_error(exc)
    2. Wraps dict results in OperationResult
    3. Avoids double-wrapping if you return OperationResult directly
    4. Returns nested data under the data_key
    """
    validated_email = validate_member_email(member_email)
    resp = self.api.add_member(group_key, validated_email)
    return {"status": "added", "email": validated_email}
```

The `@provider_operation` decorator automatically handles:
- Exception catching and classification
- Response wrapping in OperationResult
- Nesting results under data_key for response structure
- Pass-through of direct OperationResult returns to avoid double-wrapping

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
def _get_group_members_impl(self, group_key: str, **kwargs) -> List[Dict]:
    """The @provider_operation decorator automatically:
    1. Catches exceptions from _*_impl methods
    2. Classifies exceptions via self.classify_error(exc)
    3. Wraps successful dict results in OperationResult
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
# Without @provider_operation (what decorator does internally):
try:
    result = self._get_group_members_impl(group_key)
    if isinstance(result, OperationResult):
        return result  # Already wrapped
    return OperationResult(
        status=OperationStatus.SUCCESS,
        message="ok",
        data={"members": result}  # Nested under data_key
    )
except Exception as e:
    error_result = self.classify_error(e)
    return error_result
```

Benefits of using the decorator:
- Your `_*_impl` methods only need to return dicts or lists
- Exceptions are automatically classified and wrapped
- Response structure is consistent across all providers

## Configuration and Customization

Providers can be customized via configuration:

```yaml
groups:
  providers:
    my_provider:
      enabled: true
      # Optional: Override prefix used in cross-provider mapping
      prefix: "custom"
      # Optional: Override capabilities
      provides_role_info: true
      is_primary: false
```

Access configuration in your provider:

```python
from core.config import settings

class MyProvider(GroupProvider):
    def __init__(self):
        super().__init__()
        # Access provider-specific config
        provider_config = settings.groups.providers.get("my_provider", {})
        self.api_key = provider_config.get("api_key")
```

## Example: Minimal Provider Implementation

```python
from modules.groups.providers import register_provider
from modules.groups.providers.base import (
    GroupProvider,
    ProviderCapabilities,
    OperationResult,
    provider_operation,
    validate_member_email,
)

@register_provider("example")
class ExampleProvider(GroupProvider):
    """Example provider for documentation."""
    
    def __init__(self):
        super().__init__()
        self.api = ExampleAPI()  # Your API client
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            is_primary=False,
            supports_member_management=True,
            provides_role_info=False,
        )
    
    def classify_error(self, exc: Exception) -> OperationResult:
        """Classify provider-specific errors for intelligent retry logic."""
        if isinstance(exc, ExampleRateLimitError):
            return OperationResult.error(
                status=OperationStatus.TRANSIENT_ERROR,
                message="Rate limited",
                error_code="RATE_LIMITED",
                retry_after=60,
            )
        elif isinstance(exc, ExampleAuthError):
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message="Authentication failed",
                error_code="UNAUTHORIZED",
            )
        else:
            return OperationResult.error(
                status=OperationStatus.TRANSIENT_ERROR,
                message=str(exc),
            )
    
    @provider_operation(data_key="result")
    def _add_member_impl(self, group_key: str, member_email: str) -> dict:
        """Add member by email.
        
        The @provider_operation decorator:
        1. Catches exceptions and classifies them
        2. Wraps the returned dict in OperationResult
        3. Nests result under data_key="result"
        """
        validated_email = validate_member_email(member_email)
        resp = self.api.add_member(group_key, validated_email)
        return {
            "status": "added",
            "group": group_key,
            "member": validated_email,
        }
    
    @provider_operation(data_key="result")
    def _remove_member_impl(self, group_key: str, member_email: str) -> dict:
        """Remove member by email.
        
        The @provider_operation decorator handles exceptions and wrapping.
        """
        validated_email = validate_member_email(member_email)
        self.api.remove_member(group_key, validated_email)
        return {"status": "removed"}
    
    @provider_operation(data_key="members")
    def _get_group_members_impl(self, group_key: str, **kwargs) -> list:
        """Get members of a group (returns list, wrapped under data_key)."""
        members = self.api.list_members(group_key)
        return [
            {
                "email": m.get("email"),
                "id": m.get("id"),
                "role": m.get("role"),
            }
            for m in members
        ]
    
    @provider_operation(data_key="groups")
    def _list_groups_impl(self, **kwargs) -> list:
        """List all groups from provider."""
        groups = self.api.list_groups()
        return [
            {
                "id": g.get("id"),
                "name": g.get("name"),
                "email": g.get("email"),
            }
            for g in groups
        ]
    
    @provider_operation(data_key="groups")
    def _list_groups_with_members_impl(self, **kwargs) -> list:
        """List groups with members included (optional)."""
        groups = self.api.list_groups()
        return [
            {
                "id": g.get("id"),
                "name": g.get("name"),
                "members": self._get_group_members_impl(g.get("id")).data.get("members", []),
            }
            for g in groups
        ]
    
    @provider_operation(data_key="health")
    def _health_check_impl(self) -> dict:
        """Lightweight health check (minimal API call)."""
        try:
            self.api.get_status()
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
```

## Testing Your Provider

Use `@provider_operation` decorator in tests to verify error handling:

```python
import pytest
from modules.groups.providers.base import OperationResult, OperationStatus

def test_provider_handles_rate_limit():
    provider = ExampleProvider()
    
    # Mock API to raise rate limit error
    provider.api.add_member = Mock(side_effect=ExampleRateLimitError())
    
    result = provider.add_member("group1", NormalizedMember(email="user@example.com"))
    
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "RATE_LIMITED"
```

## Troubleshooting

## Migration Guide

### From Legacy Implementation

If migrating from a legacy provider implementation:

1. **Change write method signatures** to use email-based operations:
   ```python
   # Before (Legacy)
   def _add_member_impl(self, group_key: str, member_data: NormalizedMember) -> OperationResult:
   
   # After (Current)
   def _add_member_impl(self, group_key: str, member_email: str) -> dict:
   ```

2. **Add @provider_operation decorator** to all `_*_impl` methods:
   ```python
   from modules.groups.providers.base import provider_operation
   
   @provider_operation(data_key="result")
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
