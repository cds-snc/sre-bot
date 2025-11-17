Group Provider Implementation
=============================

This package provides a framework for implementing group providers that interact with identity management systems. Providers follow a standardized contract for managing group memberships across different directory services.

## Core Architecture

The provider framework consists of:

- **contracts.py** — Pure data structures for operation results and provider metadata
- **base.py** — Abstract base classes (`GroupProvider`, `PrimaryGroupProvider`) and operation lifecycle management
- **capabilities.py** — Provider capability loading and configuration
- **registry_utils.py** — Provider instantiation, configuration application, and activation utilities
- **__init__.py** — Provider discovery, registration, and activation system

## Quick Reference

- **[IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md)** — Complete guide for implementing new providers
- **[base.py](./base.py)** — Base class documentation and abstract method contracts
- **[google_workspace.py](./google_workspace.py)** — Reference implementation for Google Workspace
- **[aws_identity_center.py](./aws_identity_center.py)** — Reference implementation for AWS Identity Center

## Key Architectural Patterns

### Two-Stage Provider Lifecycle

**Stage 1: Discovery** (at module import)
- Providers register via `@register_provider()` decorator
- Classes stored in `DISCOVERED_PROVIDER_CLASSES`
- No instantiation occurs

**Stage 2: Activation** (when `load_providers()` is called)
1. Reads configuration from `settings.groups.providers`
2. Filters disabled providers
3. Instantiates providers with flexible fallback strategies
4. Applies configuration overrides
5. Validates uniqueness and determines primary provider
6. Populates `PROVIDER_REGISTRY`

### Public Method + Private `_*_impl` Pattern

All public methods have circuit breaker protection:

```python
# Public method (framework provided, circuit breaker wrapped)
def add_member(self, group_key: str, member_email: str) -> OperationResult:
    if self._circuit_breaker:
        return self._circuit_breaker.call(self._add_member_impl, group_key, member_email)
    else:
        return self._add_member_impl(group_key, member_email)

# Private implementation method (provider implements, decorated with @provider_operation)
@provider_operation(data_key="result")
def _add_member_impl(self, group_key: str, member_email: str) -> dict:
    # Your implementation returns a dict, decorator wraps it
    return {"status": "added", "email": validated_email}
```

### Email-Based Member Operations

All write operations use email addresses as the universal member identifier:

```python
@provider_operation(data_key="result")
def _add_member_impl(self, group_key: str, member_email: str) -> dict:
    validated_email = validate_member_email(member_email)  # RFC-compliant validation
    user_id = self.api.resolve_email_to_id(validated_email)  # Provider-specific mapping
    result = self.api.add_member(group_key, user_id)
    return {"status": "added", "email": validated_email}
```

Benefits:
- Consistent interface across all providers
- Email validation at provider layer
- Providers handle internal ID resolution
- Type safety with string parameters

### @provider_operation Decorator

The decorator automatically handles:
- Exception catching and classification via `classify_error()`
- Wrapping dict/list results in `OperationResult`
- Nesting results under specified `data_key`
- Pass-through of direct `OperationResult` returns (avoids double-wrapping)

```python
@provider_operation(data_key="members")
def _get_group_members_impl(self, group_key: str) -> list:
    members = self.api.list_members(group_key)
    return [{"email": m["email"], "role": m.get("role")} for m in members]
    # Automatically wrapped as: {"status": "success", "data": {"members": [...]}}
```

## Requirements for New Providers

Providers must:

- Subclass `GroupProvider` or `PrimaryGroupProvider` from `base.py`
- Be constructible without global config (no-arg `__init__()` or `from_config()` classmethod)
- Implement `@property capabilities` returning `ProviderCapabilities`
- Implement all abstract methods (`_add_member_impl`, `_remove_member_impl`, etc.)
- Decorate all `_*_impl` methods with `@provider_operation`
- Implement `classify_error()` for intelligent error handling
- Implement `_health_check_impl()` for lightweight connectivity checks
- Be registered with `@register_provider("provider_name")`

## Configuration

Providers are configured in `settings.groups.providers.*`:

```yaml
groups:
  circuit_breaker_enabled: true
  circuit_breaker_failure_threshold: 5
  providers:
    google_workspace:
      enabled: true
      domain: example.com
      is_primary: true
      provides_role_info: true
    aws_identity_center:
      enabled: true
      prefix: "aws"
```

The activation system:
1. Tries `from_config()` classmethod if available
2. Falls back to no-arg `__init__()`
3. Applies domain and capability config overrides

## Provider Activation

The framework automatically discovers and activates providers:

```python
# In app startup:
from modules.groups.providers import load_providers

primary_provider = load_providers()  # Discovers, instantiates, activates
```

Helper functions to access providers:

```python
from modules.groups.providers import (
    get_primary_provider,
    get_primary_provider_name,
    get_provider,
    get_active_providers,
)

primary = get_primary_provider()  # Get the primary provider instance
name = get_primary_provider_name()  # Get its name
custom = get_provider("aws_identity_center")  # Get specific provider
all_providers = get_active_providers()  # Get all active providers
```

## Key Framework Features

- **Email-Based Operations**: Write operations accept `member_email: str` for universal consistency
- **Circuit Breaker Protection**: Automatic protection against cascading failures in public methods
- **Unified Error Handling**: Providers classify exceptions for intelligent retry logic
- **Email Validation**: Centralized RFC 5321/5322 compliant validation via `validate_member_email()`
- **Normalization**: Providers convert provider-specific schemas to canonical models
- **Health Checks**: Built-in health check operations for monitoring provider connectivity
- **Primary/Secondary Pattern**: One canonical provider plus optional secondary providers with cross-provider synchronization

## Testing Your Provider

Mock the API and verify error classification:

```python
import pytest
from modules.groups.providers.base import OperationStatus

def test_provider_handles_rate_limit():
    provider = MyProvider()
    provider.api = Mock()
    provider.api.add_member.side_effect = MyRateLimitError(retry_after=30)
    
    result = provider.add_member("group1", "user@example.com")
    
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "RATE_LIMITED"
    assert result.retry_after == 30
```

## Getting Started

See [IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md) for:

- Step-by-step implementation instructions
- Complete provider contract specification
- Code examples and patterns
- Email validation and error classification
- Testing strategies
- Configuration options
