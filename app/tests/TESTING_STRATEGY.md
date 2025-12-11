# Testing Strategy and Structure

This document contains the new testing strategy and structure to implement within the `app/tests/` directory. It outlines the organization of test files, fixture hierarchy, factory patterns, and fake client implementations to ensure maintainable, efficient, and reliable tests.

## Environment Variables

All the environment variables loading have been migrated to a centralized location in `core.config.settings`. Tests should not rely on loading `.env` files directly or trying to mock those. Instead, use the settings module to access configuration values. If specific environment variables are needed for tests, they should be mocked or set within the test setup using fixtures.

## Pytest Configuration

All pytest configuration is centralized in `/workspace/app/pytest.ini`. Key settings:

**Test Discovery:**
- `testpaths = tests` - Tests discovered under `/workspace/app/tests/`
- `norecursedirs = tests/smoke` - Smoke tests not run by default (require explicit credentials)

**Markers for Test Organization:**
- `@pytest.mark.unit` - Pure unit tests with no external dependencies
- `@pytest.mark.integration` - Integration tests combining multiple components
- `@pytest.mark.legacy` - Legacy test structure maintained during transition

**Environment:**
- All environment variables pre-configured in pytest.ini
- Tests can reference variables via `settings` object from `core.config`
- No `.env` file loading required for tests

**Run Tests:**
```bash
# All tests
pytest

# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Specific module
pytest tests/unit/modules/groups/

# With coverage
pytest --cov=modules.groups --cov-report=html
```

## Directory Structure

The current test directory structure separates concerns clearly with predictable organization:

```plaintext
tests/
├── conftest.py                      # Root-level shared fixtures (Level 1)
├── pytest.ini                       # Pytest configuration
├── factories/                       # Test data factories
│   ├── __init__.py
│   ├── aws.py                       # AWS test data builders
│   ├── commands.py                  # Command framework data builders
│   ├── google.py                    # Google test data builders
│   ├── groups_commands.py           # Groups command data builders
│   └── i18n.py                      # i18n test data builders
├── fixtures/                        # Reusable fake clients
│   ├── __init__.py
│   ├── aws_clients.py               # FakeClient for AWS SDK
│   └── google_clients.py            # FakeGoogleService
├── unit/                            # Pure unit tests
│   ├── infrastructure/
│   │   ├── conftest.py              # Infrastructure module-level fixtures
│   │   ├── commands/
│   │   │   ├── conftest.py          # Commands feature-level fixtures (Level 3)
│   │   │   ├── providers/
│   │   │   │   ├── conftest.py      # Slack provider fixtures (Level 4)
│   │   │   │   ├── test_base.py
│   │   │   │   ├── test_providers.py
│   │   │   │   └── test_slack.py
│   │   │   ├── responses/
│   │   │   │   ├── test_models.py
│   │   │   │   └── test_slack_formatter.py
│   │   │   ├── test_context.py
│   │   │   ├── test_models.py
│   │   │   ├── test_parser.py
│   │   │   └── test_registry.py
│   │   ├── i18n/
│   │   │   ├── conftest.py          # i18n module fixtures
│   │   │   ├── test_loader.py
│   │   │   ├── test_models.py
│   │   │   ├── test_resolvers.py
│   │   │   └── test_translator.py
│   │   ├── plugins/
│   │   ├── test_circuit_breaker.py
│   │   └── test_operations_result.py
│   └── modules/
│       ├── groups/
│       │   ├── conftest.py          # Groups module-level fixtures (Level 2)
│       │   ├── commands/
│       │   │   └── test_registry.py
│       │   ├── providers/
│       │   │   ├── conftest.py      # Providers feature-level fixtures (Level 3)
│       │   │   ├── test_aws_identity_center.py
│       │   │   ├── test_base_provider.py
│       │   │   ├── test_google_workspace_provider.py
│       │   │   └── test_provider_registry.py
│       │   ├── test_audit.py
│       │   ├── test_errors.py
│       │   ├── test_event_system.py
│       │   ├── test_idempotency.py
│       │   ├── test_models.py
│       │   ├── test_orchestration.py
│       │   ├── test_reconciliation.py
│       │   ├── test_schemas.py
│       │   ├── test_service_permissions.py
│       │   └── test_validation.py
│       └── sre/
│           ├── conftest.py          # SRE module fixtures
│           ├── test_geolocate_helper.py
│           └── test_webhook_helper.py
├── integration/                     # Integration tests
│   ├── conftest.py                  # Root integration fixtures
│   ├── infrastructure/
│   │   └── commands/
│   │       ├── test_provider_integration.py
│   │       ├── test_response_integration.py
│   │       └── test_router_quote_preservation.py
│   └── modules/
│       ├── groups/
│       │   ├── conftest.py          # Groups module fixtures
│       │   ├── commands/
│       │   │   └── test_command_integration.py
│       │   ├── providers/
│       │   │   ├── conftest.py      # Provider integration fixtures
│       │   │   └── (provider integration tests)
│       │   ├── test_controllers_integration.py
│       │   ├── test_orchestration_integration.py
│       │   ├── test_reconciliation_integration.py
│       │   ├── test_service_audit_integration.py
│       │   └── test_service_integration.py
│       └── sre/
│           ├── conftest.py          # SRE integration fixtures
│           ├── test_sre_providers.py
│           └── (other tests)
└── (other test directories)
```

### Directory Purpose

#### `tests/unit/`

Pure unit tests that:

- Test individual functions/classes in isolation
- Use mocks for all external dependencies
- Execute in <50ms per test
- Do not perform I/O operations (no network, filesystem, database)
- Follow naming: `test_<function_name>_<scenario>.py`

#### `tests/integration/`

Integration tests that:

- Test interactions between multiple components
- May use real clients with stubbed responses
- Verify data flow through system layers
- Test provider integration with service layer
- Execute in <500ms per test
- Follow naming: `test_<feature>_integration.py`

#### `tests/factories/`

Factory functions that create valid test data:

- Return plain dicts or Pydantic models
- Parameterized for flexibility
- Immutable and deterministic
- No state or side effects

#### `tests/fixtures/`

Reusable fake client implementations:

- `FakeClient`: AWS SDK mock with paginator support
- `FakeGoogleService`: Google API resource mock
- Configurable responses per method

## Fixture Hierarchy

### Layered Fixture Architecture

Fixtures are organized in a layered hierarchy to manage scope and dependencies:

```plaintext
tests/conftest.py                           # Level 1: Global fixtures
    ↓
tests/unit/modules/<module>/conftest.py     # Level 2: Module-level fixtures
    ↓
tests/unit/modules/<module>/<feature>/conftest.py  # Level 3: Feature-level fixtures
    ↓
tests/unit/infrastructure/<component>/conftest.py  # Level 3+: Component-level fixtures
```

**Fixture Scope Conventions:**
- `function` (default): New instance per test - use for mutable state
- `module`: Shared across test file - use for expensive setup or immutable data
- `session`: Shared across entire test run - use for static configuration only
- `autouse`: Applied automatically to all tests in scope - use sparingly, document clearly

### Level 1: Global Fixtures - `tests/conftest.py`

Root-level fixtures available to all tests (530 lines).

**Session Setup & Mocking:**
- `pytest_configure()` - Mocks Slack App before imports to prevent auth errors during collection
- `suppress_structlog_output` (autouse) - Suppresses application logging during tests for clean output

**Provider & Registry Management:**
- `reset_provider_registries` - Resets provider registries between tests (non-autouse, use as needed)

**Test Data Factories:**
- `google_group_factory()`, `google_user_factory()`, `google_member_factory()` - Google Workspace test data
- `aws_user_factory()`, `aws_group_factory()` - AWS Identity Center test data
- `argument_factory()`, `command_factory()`, `command_context_factory()`, `command_registry_factory()` - Command framework test data

**Provider Configuration:**
- `mock_provider_config()` - Base factory for provider configuration dictionaries
- `single_provider_config()` - Single primary provider configuration
- `multi_provider_config()` - Multiple providers (Google primary, AWS secondary)
- `disabled_provider_config()` - Mixed enabled/disabled provider setup

**Legacy Fixtures (backward compatibility):**
- `google_groups()`, `google_users()`, `google_group_members()`, `google_groups_w_users()`
- `aws_users()`, `aws_groups()`, `aws_groups_w_users_with_legacy()`

Use factories instead of legacy fixtures for new tests.

### Level 2: Module Fixtures

Each module has its own conftest at `tests/unit/modules/<module>/conftest.py` containing:

**Module `groups` - `/tests/unit/modules/groups/conftest.py`**
- Mock provider implementations: `MockPrimaryGroupProvider`, `MockGroupProvider`
- Settings mocks: `mock_settings_groups`, `mock_settings_groups_disabled_cb`
- Domain model factories: `normalized_member_factory()`, `normalized_group_factory()`, `operation_result_factory()`
- Provider registry fixtures: `mock_providers_registry`, `mock_primary_provider()`, `mock_secondary_provider()`

**Module `sre` - `tests/unit/modules/sre/conftest.py`**
- Slack mocks: `mock_respond()`, `mock_client()`, `mock_body()`

### Level 3: Feature/Component Fixtures

Features within modules have their own conftest at `tests/unit/modules/<module>/<feature>/conftest.py` or `tests/unit/infrastructure/<component>/conftest.py`:

**Providers Feature - `tests/unit/modules/groups/providers/conftest.py`**
- Mock API clients: `mock_google_directory_client()`, `mock_identity_store_client()`
- Sample test data: `sample_google_group_data()`, `sample_google_member_data()`, `sample_aws_group_data()`, `sample_aws_member_data()`
- Capability/result factories: `provider_capabilities_factory()`, `operation_result_factory()`
- Mock provider classes: `mock_primary_class()`, `mock_secondary_class()`

**Commands - `tests/unit/infrastructure/commands/conftest.py`**
- Context factory: `command_context_factory()`
- Mock functions: `mock_translator()`, `mock_response_channel()`, `mock_slack_client()`, `mock_slack_respond()`, `mock_slack_ack()`
- Parser: `command_parser`
- Sample data: `slack_command_payload`

**Slack Provider - `tests/unit/infrastructure/commands/providers/conftest.py`**
- `mock_slack_settings` (autouse) - Enables SlackCommandProvider instantiation without credentials

**i18n - `tests/unit/infrastructure/i18n/conftest.py`**
- Internationalization-specific fixtures for loader, models, resolvers, and translator testing

```python
# tests/unit/modules/groups/conftest.py
import types
from typing import Dict, Any
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_settings_groups():
    """Mock core.config.settings with groups configuration.
    
    Returns a SimpleNamespace mimicking settings structure with
    groups attribute containing circuit breaker config and providers dict.
    
    Usage:
        def test_something(mock_settings_groups, monkeypatch):
            monkeypatch.setattr("core.config.settings", mock_settings_groups)
            # Test code that accesses settings.groups
    """
    return types.SimpleNamespace(
        groups=types.SimpleNamespace(
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_timeout_seconds=60,
            circuit_breaker_half_open_max_calls=3,
            providers={},
        )
    )


@pytest.fixture
def mock_settings_groups_disabled_cb():
    """Mock settings with circuit breaker disabled."""
    return types.SimpleNamespace(
        groups=types.SimpleNamespace(
            circuit_breaker_enabled=False,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_timeout_seconds=60,
            circuit_breaker_half_open_max_calls=3,
            providers={},
        )
    )


@pytest.fixture
def normalized_member_factory():
    """Factory for creating NormalizedMember instances.
    
    Usage:
        member = normalized_member_factory(
            email="test@example.com",
            role="member"
        )
    """
    from modules.groups.models import NormalizedMember
    
    def _factory(
        email: str = "test@example.com",
        id: str = "user-1",
        role: str = "member",
        provider_member_id: str = "provider-1",
        first_name: str = None,
        family_name: str = None,
        raw: Dict[str, Any] = None,
    ) -> NormalizedMember:
        return NormalizedMember(
            email=email,
            id=id,
            role=role,
            provider_member_id=provider_member_id,
            first_name=first_name,
            family_name=family_name,
            raw=raw,
        )
    
    return _factory


@pytest.fixture
def normalized_group_factory():
    """Factory for creating NormalizedGroup instances.
    
    Usage:
        group = normalized_group_factory(
            id="group-123",
            name="Test Group"
        )
    """
    from modules.groups.models import NormalizedGroup
    
    def _factory(
        id: str = "group-1",
        name: str = "Test Group",
        description: str = "Test description",
        provider: str = "test",
        email: str = None,
        members: list = None,
        raw: Dict[str, Any] = None,
    ) -> NormalizedGroup:
        return NormalizedGroup(
            id=id,
            name=name,
            description=description,
            provider=provider,
            email=email,
            members=members or [],
            raw=raw,
        )
    
    return _factory


@pytest.fixture
def operation_result_factory():
    """Factory for creating OperationResult instances.
    
    Usage:
        result = operation_result_factory(
            status=OperationStatus.SUCCESS,
            data={"added": True}
        )
    """
    from modules.groups.providers.base import OperationResult, OperationStatus
    
    def _factory(
        status: OperationStatus = OperationStatus.SUCCESS,
        message: str = "ok",
        data: Dict[str, Any] = None,
        error_code: str = None,
        retry_after: int = None,
    ) -> OperationResult:
        return OperationResult(
            status=status,
            message=message,
            data=data,
            error_code=error_code,
            retry_after=retry_after,
        )
    
    return _factory


@pytest.fixture
def mock_provider_config():
    """Factory for creating provider configuration dicts.
    
    Usage:
        config = mock_provider_config(
            provider_name="google",
            enabled=True,
            primary=True
        )
    """
    def _factory(
        provider_name: str,
        enabled: bool = True,
        primary: bool = False,
        prefix: str = None,
        capabilities: dict = None,
    ) -> dict:
        config = {"enabled": enabled}
        
        if primary:
            config["primary"] = True
        
        if prefix:
            config["prefix"] = prefix
        
        if capabilities:
            config["capabilities"] = capabilities
        
        return {provider_name: config}
    
    return _factory


@pytest.fixture
def single_provider_config(mock_provider_config):
    """Provider configuration with single enabled primary provider."""
    return mock_provider_config(
        provider_name="google",
        enabled=True,
        primary=True,
        capabilities={
            "supports_member_management": True,
            "provides_role_info": True
        },
    )


@pytest.fixture
def multi_provider_config(mock_provider_config):
    """Provider configuration with multiple enabled providers."""
    google_cfg = mock_provider_config(
        provider_name="google",
        enabled=True,
        primary=True,
        capabilities={
            "supports_member_management": True,
            "provides_role_info": True
        },
    )
    
    aws_cfg = mock_provider_config(
        provider_name="aws",
        enabled=True,
        primary=False,
        prefix="aws",
        capabilities={
            "supports_member_management": True,
            "supports_batch_operations": True,
            "max_batch_size": 100,
        },
    )
    
    return {**google_cfg, **aws_cfg}
```

## Factory Pattern

### Factory Implementation

Factories create test data deterministically without side effects:

```python
# tests/factories/google.py
from integrations.google_workspace.schemas import Group, User, Member


def make_google_groups(n=3, prefix="", domain="test.com", as_model=False):
    """Create test Google Group data.
    
    Args:
        n: Number of groups to create
        prefix: String prefix for all IDs and names
        domain: Email domain
        as_model: Return Pydantic models if True, dicts if False
    
    Returns:
        List of Group models or dicts
    """
    groups = []
    for i in range(n):
        g = Group(
            kind="admin#directory#group",
            id=f"{prefix}google_group_id{i+1}",
            etag=f'"group-etag-{i+1}"',
            name=f"{prefix}group-name{i+1}",
            email=f"{prefix}group-name{i+1}@{domain}",
            description=f"{prefix}description{i+1}",
            directMembersCount=i + 1,
            adminCreated=False,
            nonEditableAliases=[f"{prefix}noneditable-group{i+1}@{domain}"],
            members=[],
        )
        groups.append(g)
    
    return groups if as_model else [g.model_dump() for g in groups]


def make_google_users(n=3, prefix="", domain="test.com", as_model=False):
    """Create test Google User data.
    
    Args:
        n: Number of users to create
        prefix: String prefix for all IDs and emails
        domain: Email domain
        as_model: Return Pydantic models if True, dicts if False
    
    Returns:
        List of User models or dicts
    """
    users = []
    for i in range(n):
        u = User(
            id=f"{prefix}user_id{i+1}",
            primaryEmail=f"{prefix}user-email{i+1}@{domain}",
            emails=[{
                "address": f"{prefix}user-email{i+1}@{domain}",
                "primary": True,
                "type": "work",
            }],
            suspended=False,
            name={
                "fullName": f"Given_name_{i+1} Family_name_{i+1}",
                "familyName": f"Family_name_{i+1}",
                "givenName": f"Given_name_{i+1}",
            },
            aliases=[f"{prefix}alias{i+1}@{domain}"],
            customerId=f"C0{i+1}cust",
            orgUnitPath="/Products",
            isAdmin=False,
            agreedToTerms=True,
            archived=False,
            isMailboxSetup=True,
        )
        users.append(u)
    
    return users if as_model else [u.model_dump() for u in users]


def make_google_members(n=3, prefix="", domain="test.com", as_model=False):
    """Create test Google Member data.
    
    Members are users with group membership metadata.
    
    Args:
        n: Number of members to create
        prefix: String prefix for all IDs
        domain: Email domain
        as_model: Return Pydantic models if True, dicts if False
    
    Returns:
        List of Member models or dicts
    """
    users = make_google_users(n, prefix=prefix, domain=domain, as_model=True)
    members = []
    for i, user in enumerate(users):
        m = Member(
            kind="admin#directory#member",
            etag=f'"member-etag-{i+1}"',
            id=user.id,
            email=user.primaryEmail,
            role="MEMBER",
            type="USER",
            status="ACTIVE",
            user=user,
            primaryEmail=user.primaryEmail,
            name=user.name.model_dump() if user.name else None,
            isAdmin=False,
        )
        members.append(m)
    
    return members if as_model else [m.model_dump() for m in members]
```

## Integration Test Fixtures

### Integration Test Fixture Hierarchy

Integration test fixtures follow a layered architecture similar to unit tests:

```plaintext
tests/integration/conftest.py                           # Infrastructure-wide mocks (autouse)
    ↓
tests/integration/modules/<module>/conftest.py          # Module-specific integration mocks
    ↓
tests/integration/<area>/<component>/conftest.py        # Component-specific integration mocks
```

**Fixture Placement Rules:**
1. **Root Integration Conftest** (`tests/integration/conftest.py`):
   - Infrastructure-wide system boundary mocks (DynamoDB, Sentinel, external APIs)
   - Autouse fixtures that prevent actual I/O for all integration tests
   - Generic test utilities used across all modules

2. **Module Integration Conftest** (`tests/integration/modules/<module>/conftest.py`):
   - Module-specific orchestration mocks
   - Module-specific event system mocks
   - Module-specific validation mocks
   - Module domain fixtures and test data

3. **Component Integration Conftest** (`tests/integration/<area>/<component>/conftest.py`):
   - Component-specific configuration
   - Component-specific test scenarios
   - Fine-grained mocks for specific features

### Root Integration `tests/integration/conftest.py`

Integration-level fixtures for **infrastructure-wide** system boundary mocking. Location: `/workspace/app/tests/integration/conftest.py`

**Autouse Fixtures (Applied Automatically):**
- `_autouse_mock_dynamodb_audit` - Automatically mocks `infrastructure.events.handlers.audit.dynamodb_audit.write_audit_event` to prevent actual DynamoDB writes during all integration tests
- `_autouse_mock_sentinel_client` - Automatically mocks `integrations.sentinel.client.log_to_sentinel` and `integrations.sentinel.client.log_audit_event` to prevent actual Sentinel calls during all integration tests

**Note:** These autouse fixtures ensure that integration tests never write to actual external systems (DynamoDB, Sentinel). Tests can still assert on these mocks by using `monkeypatch` to override them if needed.

**Manual Request Fixtures:**
- `mock_sentinel_client` - Explicit Sentinel client mock for tests that need to assert on Sentinel calls (most tests use the autouse fixture automatically)

**Module-Specific Fixtures:**
Module-specific fixtures (e.g., groups orchestration, event dispatch) are documented in their respective module conftest files under `tests/integration/modules/<module>/conftest.py`

### Module Integration `tests/integration/modules/groups/conftest.py`

Module-level integration fixtures for groups. Location: `/workspace/app/tests/integration/modules/groups/conftest.py`

**Orchestration Layer Mocks:**
- `mock_orchestration` - Configurable mock orchestration layer for add/remove member operations
  - Patches: `modules.groups.core.orchestration.add_member_to_group` and `modules.groups.core.orchestration.remove_member_from_group`
  - Returns: Namespace with `add_member` and `remove_member` mocks
  - Default behavior: Success responses

**Event System Mocks:**
- `mock_event_dispatch` - Captures dispatched events for groups operations
  - Patches: `modules.groups.core.service.dispatch_background` (legacy)
  - Should be migrated to patch `infrastructure.events.dispatch_event` (centralized)
  - Provides: `get_dispatched()` and `clear_dispatched()` methods

- `mock_event_system` - Complete event system mock for groups
  - Patches: `modules.groups.events.dispatch_event` (legacy)
  - **TODO**: Update to patch `infrastructure.events.dispatch_event` after event system migration completes
  - Provides: dispatch, subscribe, get_dispatched, get_subscribers, clear methods

**Validation Layer Mocks:**
- `mock_validation_success` - Mocks validation to always pass
- `mock_validation_failure` - Mocks validation to return errors

**Service Access:**
- `groups_module` - Direct import of groups service module
- `groups_orchestration` - Direct import of orchestration module
- `groups_validation` - Direct import of validation module

**Integration Test Context:**
- `integration_test_context` - Pre-configured context with orchestration, events, and validation mocked
- `isolated_group_service` - Groups service with all external boundaries mocked

**Note:** These fixtures are **groups-specific** and only available to tests under `tests/integration/modules/groups/`. They extend the root integration fixtures with groups domain knowledge.

### Module Integration `tests/integration/modules/sre/conftest.py`

Module-level integration fixtures for SRE:
- `mock_respond` - Mock Slack respond function
- `mock_ack` - Mock Slack ack function
- `mock_client` - Mock Slack client

### Factory Usage Patterns

```python
def test_list_groups_returns_normalized_groups(google_group_factory):
    """Test using factory fixture from root conftest."""
    # Factory creates 3 groups by default
    raw_groups = google_group_factory()
    assert len(raw_groups) == 3
    assert all(isinstance(g, dict) for g in raw_groups)
    
    # Customize parameters
    custom_groups = google_group_factory(n=5, prefix="test-", as_model=True)
    assert len(custom_groups) == 5
    assert custom_groups[0].name == "test-group-name1"


def test_member_normalization(google_member_factory, normalized_member_factory):
    """Test using multiple factories together."""
    # Raw Google data
    raw_members = google_member_factory(n=2, domain="example.com")
    
    # Normalized domain models
    normalized = [
        normalized_member_factory(
            email=m["email"],
            id=m["id"],
            role=m["role"].lower()
        )
        for m in raw_members
    ]
    
    assert len(normalized) == 2
    assert all(m.email.endswith("@example.com") for m in normalized)
```

## Fake Client Pattern

### FakeClient for AWS SDK

```python
# tests/fixtures/aws_clients.py
from typing import Any, Iterable, List


class FakePaginator:
    """Simulates boto3 paginator."""
    
    def __init__(self, pages: Iterable[dict]):
        self._pages = list(pages)
    
    def paginate(self, **kwargs):
        for page in self._pages:
            yield page


class FakeClient:
    """Simulates boto3 client for testing.
    
    Supports:
    - API method stubs via api_responses dict
    - Pagination via paginated_pages list
    - can_paginate() checks
    
    Usage:
        client = FakeClient(
            api_responses={
                "describe_user": {"UserId": "u-1", "UserName": "test"},
                "create_user": lambda **kw: {"UserId": "new-id"},
            },
            paginated_pages=[
                {"Users": [{"UserId": "u-1"}], "NextToken": "tok1"},
                {"Users": [{"UserId": "u-2"}]},
            ]
        )
        
        # Use like real boto3 client
        user = client.describe_user(UserId="u-1")
        paginator = client.get_paginator("list_users")
        for page in paginator.paginate():
            users = page["Users"]
    """
    
    def __init__(
        self,
        paginated_pages: List[dict] | None = None,
        api_responses: dict | None = None,
        can_paginate: Any = None,
    ):
        self._paginated_pages = paginated_pages or []
        self._api_responses = api_responses or {}
        
        if can_paginate is None:
            self._can_paginate = bool(self._paginated_pages)
        else:
            self._can_paginate = can_paginate
    
    def get_paginator(self, *args, **kwargs):
        if not self._paginated_pages:
            raise AttributeError("No paginator available")
        return FakePaginator(self._paginated_pages)
    
    def __getattr__(self, name: str):
        if name in self._api_responses:
            resp = self._api_responses[name]
            
            if callable(resp):
                def _call(*_args: Any, **_kwargs: Any):
                    return resp(**_kwargs)
                return _call
            
            def _call_const(*_args: Any, **_kwargs: Any):
                return resp
            return _call_const
        
        if self._paginated_pages:
            def _noop(*_args: Any, **_kwargs: Any):
                return {}
            return _noop
        
        raise AttributeError(name)
    
    def can_paginate(self, method_name: str) -> bool:
        if callable(self._can_paginate):
            try:
                return bool(self._can_paginate(method_name))
            except Exception:
                return False
        return bool(self._can_paginate)
```

### FakeClient Usage

```python
def test_list_users_with_pagination(fake_aws_client, monkeypatch):
    """Test AWS integration using FakeClient."""
    # Create client with paginated responses
    client = fake_aws_client(
        paginated_pages=[
            {"Users": [{"UserId": "u-1", "UserName": "alice"}], "NextToken": "t1"},
            {"Users": [{"UserId": "u-2", "UserName": "bob"}]},
        ]
    )
    
    # Patch boto3 client creation
    monkeypatch.setattr(
        "integrations.aws.identity_store.get_client",
        lambda service: client
    )
    
    # Test code that uses identity_store
    from integrations.aws import identity_store
    users = identity_store.list_users()
    
    assert len(users) == 2
    assert users[0]["UserName"] == "alice"


def test_create_user_with_callable_response(fake_aws_client, monkeypatch):
    """Test with dynamic response based on input."""
    def create_response(**kwargs):
        return {
            "UserId": "new-id",
            "UserName": kwargs.get("UserName", "unknown")
        }
    
    client = fake_aws_client(
        api_responses={"create_user": create_response}
    )
    
    monkeypatch.setattr("integrations.aws.identity_store.get_client", lambda s: client)
    
    from integrations.aws import identity_store
    result = identity_store.create_user(
        email="test@example.com",
        first_name="Test",
        last_name="User"
    )
    
    assert result["UserId"] == "new-id"
```

## Test Organization Rules

### Import Organization

**Always import at module level** unless technically required inline (e.g., avoiding circular imports).

Follow PEP 8 import guidelines:
- Standard library imports first
- Third-party imports second  
- Local application imports third
- Blank line between each group

**Exception Imports:**
Always import exceptions at the top of test modules, not inline within test functions:

```python
# ✅ CORRECT - Top-level import
import pytest
from pydantic import ValidationError

from infrastructure.notifications.models import Recipient


class TestRecipient:
    def test_recipient_requires_email(self):
        """Email is required by Pydantic at Recipient creation."""
        with pytest.raises(ValidationError, match="email"):
            Recipient()
    
    def test_recipient_validates_email_format(self):
        """Invalid email format is rejected by Pydantic."""
        with pytest.raises(ValidationError, match="email"):
            Recipient(email="not-an-email")
```

```python
# ❌ INCORRECT - Inline import
import pytest

from infrastructure.notifications.models import Recipient


class TestRecipient:
    def test_recipient_requires_email(self):
        """Email is required by Pydantic at Recipient creation."""
        from pydantic import ValidationError  # Don't do this!
        
        with pytest.raises(ValidationError, match="email"):
            Recipient()
```

**Rationale:**
- Follows Python conventions (PEP 8)
- Makes dependencies explicit and visible
- Reduces code duplication
- Improves IDE autocomplete and static analysis
- Simplifies debugging (import errors fail fast at module load)

**When inline imports are acceptable:**
- Breaking circular import dependencies
- Conditional imports based on environment or feature flags
- Heavy imports only used in specific test paths
- These cases should be documented with comments explaining why

### Naming Conventions

```plaintext
test_<function/class>_<scenario>.py           # Unit test file
test_<feature>_integration.py                 # Integration test file
test_<provider>_provider.py                   # Provider tests
test_<module>_<subfeature>.py                 # Subfeature tests
```

### File Organization

```python
# tests/unit/modules/groups/test_models.py

"""Unit tests for groups module data models.

Tests cover:
- NormalizedMember creation and validation
- NormalizedGroup creation and validation
- Model conversion methods (to_dict, from_dict)
- Edge cases (missing fields, invalid data)
"""

import pytest
from modules.groups.models import NormalizedMember, NormalizedGroup


class TestNormalizedMember:
    """Tests for NormalizedMember model."""
    
    def test_member_creation_with_all_fields(self, normalized_member_factory):
        """Member can be created with all fields populated."""
        member = normalized_member_factory(
            email="test@example.com",
            id="user-123",
            role="member",
            first_name="Test",
            family_name="User"
        )
        
        assert member.email == "test@example.com"
        assert member.id == "user-123"
        assert member.role == "member"
        assert member.first_name == "Test"
        assert member.family_name == "User"
    
    def test_member_creation_with_minimal_fields(self):
        """Member can be created with only required fields."""
        member = NormalizedMember(
            email="test@example.com",
            id="user-123",
            role="member",
            provider_member_id="pm-123"
        )
        
        assert member.email == "test@example.com"
        assert member.first_name is None
        assert member.family_name is None
    
    def test_member_invalid_email_raises(self):
        """Invalid email format raises validation error."""
        with pytest.raises(ValueError, match="email"):
            NormalizedMember(
                email="not-an-email",
                id="user-123",
                role="member",
                provider_member_id="pm-123"
            )


class TestNormalizedGroup:
    """Tests for NormalizedGroup model."""
    
    def test_group_creation(self, normalized_group_factory):
        """Group can be created with factory."""
        group = normalized_group_factory(
            id="group-1",
            name="Test Group",
            provider="google"
        )
        
        assert group.id == "group-1"
        assert group.name == "Test Group"
        assert group.provider == "google"
        assert group.members == []
    
    def test_group_with_members(self, normalized_group_factory, normalized_member_factory):
        """Group can contain member list."""
        members = [
            normalized_member_factory(email=f"user{i}@example.com")
            for i in range(3)
        ]
        
        group = normalized_group_factory(members=members)
        
        assert len(group.members) == 3
        assert all(hasattr(m, "email") for m in group.members)
```

### Test Class Organization

Use test classes to group related tests:

```python
class TestProviderInitialization:
    """Tests for provider initialization and configuration."""
    
    def test_provider_loads_config_from_settings(self): ...
    def test_provider_raises_on_missing_config(self): ...
    def test_provider_circuit_breaker_enabled_by_default(self): ...


class TestProviderMemberOperations:
    """Tests for add/remove member operations."""
    
    def test_add_member_success(self): ...
    def test_add_member_duplicate_is_idempotent(self): ...
    def test_remove_member_success(self): ...
    def test_remove_member_nonexistent_fails(self): ...


class TestProviderGroupOperations:
    """Tests for list groups operations."""
    
    def test_list_groups_returns_normalized(self): ...
    def test_list_groups_empty(self): ...
    def test_get_group_members(self): ...
```

## Pytest Configuration

```ini
# tests/pytest.ini
[pytest]
minversion = 7.0
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Markers for test categorization
markers =
    unit: Pure unit tests (fast, isolated)
    integration: Integration tests (slower, multi-component)
    slow: Tests that take >1s to execute
    external: Tests that require external services
    smoke: Smoke tests for critical paths

# Output options
addopts =
    -ra
    --strict-markers
    --strict-config
    --showlocals
    --tb=short

# Coverage options (when using pytest-cov)
[coverage:run]
source = app/
omit =
    */tests/*
    */migrations/*
    */__pycache__/*

[coverage:report]
precision = 2
show_missing = True
skip_covered = False
```

### Running Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific module unit tests
pytest tests/unit/modules/groups/ -v

# Run integration tests
pytest tests/integration/ -v

# Run with markers
pytest -m unit
pytest -m integration
pytest -m "not slow"

# Run with coverage
pytest tests/unit/ --cov=modules.groups --cov-report=html

# Run specific test class
pytest tests/unit/modules/groups/test_models.py::TestNormalizedMember -v

# Run specific test
pytest tests/unit/modules/groups/test_models.py::TestNormalizedMember::test_member_creation_with_all_fields -v
```

## Mocking Strategy

### Import-Time vs Runtime Patching

```python
# AVOID: Patching at import time (fragile)
from unittest.mock import patch

with patch("module.dependency"):
    from module import function_to_test


# PREFER: Patching at runtime (explicit)
def test_function(monkeypatch):
    """Use monkeypatch fixture for clear, scoped patches."""
    monkeypatch.setattr("module.dependency", mock_value)
    from module import function_to_test
    result = function_to_test()
```

### Patching Layers

Patch at the boundary between your code and external systems:

```python
# AVOID: Patching deep in external library
def test_list_groups(monkeypatch):
    monkeypatch.setattr("googleapiclient.discovery.build", mock_build)


# PREFER: Patch your integration layer
def test_list_groups(monkeypatch):
    monkeypatch.setattr(
        "integrations.google_workspace.google_directory.list_groups",
        lambda: [{"id": "g-1"}]
    )
```

### Mock Configuration

```python
def test_with_configured_mock():
    """Configure mocks explicitly for clarity."""
    from unittest.mock import MagicMock
    
    mock_client = MagicMock()
    mock_client.list_groups.return_value = {"groups": []}
    mock_client.get_group.return_value = {"id": "g-1", "name": "Test"}
    
    # Use configured mock
    provider = GoogleWorkspaceProvider()
    provider.integration = mock_client
    
    result = provider.list_groups()
    
    mock_client.list_groups.assert_called_once()
```

## Assertion Patterns

### Descriptive Assertions

```python
# AVOID: Generic assertions
assert result == expected

# PREFER: Descriptive assertions with context
assert result.success is True, f"Expected success, got: {result}"
assert len(result.members) == 3, "Should have 3 members"
assert "error" not in result.data, f"Unexpected error: {result.data.get('error')}"
```

### Assertion Helpers

```python
def assert_normalized_member(member, expected_email):
    """Helper for complex member assertions."""
    assert hasattr(member, "email"), "Member missing email attribute"
    assert member.email == expected_email
    assert member.id is not None, "Member missing ID"
    assert member.role in ["member", "manager", "owner"]


def test_member_normalization():
    result = normalize_member({"email": "test@example.com"})
    assert_normalized_member(result, "test@example.com")
```

## Test Data Management

### Immutable Test Data

```python
# tests/testdata/groups.json
{
  "google_group_basic": {
    "id": "g-basic",
    "name": "basic-group",
    "email": "basic@example.com"
  },
  "aws_group_basic": {
    "GroupId": "ag-basic",
    "DisplayName": "basic-group"
  }
}
```

```python
import json

@pytest.fixture(scope="session")
def test_groups_data(test_data_dir):
    """Load immutable test data from JSON."""
    with open(test_data_dir / "groups.json") as f:
        return json.load(f)


def test_with_static_data(test_groups_data):
    """Use static test data for deterministic tests."""
    google_group = test_groups_data["google_group_basic"]
    assert google_group["name"] == "basic-group"
```

### Parameterized Tests

```python
@pytest.mark.parametrize("email,expected_local", [
    ("user@example.com", "user"),
    ("user.name@example.com", "user.name"),
    ("user+tag@example.com", "user+tag"),
    ("", ""),
    (None, None),
])
def test_extract_local_part(email, expected_local):
    """Test email local part extraction with multiple inputs."""
    result = extract_local_part(email)
    assert result == expected_local


@pytest.mark.parametrize("provider,group_id,expected", [
    ("google", "group-1", "group-1"),
    ("aws", "aws:group-1", "group-1"),
    ("aws", "group-1", "aws:group-1"),
])
def test_map_provider_group_id(provider, group_id, expected):
    """Test group ID mapping across providers."""
    result = map_provider_group_id(provider, group_id)
    assert result == expected
```

This testing strategy provides a foundation for maintainable, readable tests that follow industry best practices while being tailored to the SRE Bot codebase structure.


## Testing Best Practices

### When to Create New Tests

- **Unit tests** (`@pytest.mark.unit`): When testing individual functions/classes in isolation with mocks
- **Integration tests** (`@pytest.mark.integration`): When testing interactions between components or with stubbed services
- Place tests in appropriate module under `tests/unit/` or `tests/integration/` following existing structure
- Run `make fmt` and `make lint` (from `/workspace/app`) before committing test changes

### Fixture Naming & Organization

- Fixture names should be descriptive: `mock_primary_provider`, `google_groups_factory`, `command_context_factory`
- Autouse fixtures should be minimal and well-documented; prefer explicit fixture injection
- Group related fixtures at appropriate levels (root for global, module for domain-specific)
- Avoid fixture duplication across levels; inherit from parent conftest when possible

### Mocking Strategy

- Mock at system boundaries (integration layers, external services)
- Prefer explicit mocking via `monkeypatch` over import-time patching
- Use `@unittest.mock.patch` for third-party library mocking
- Create reusable mock factories for complex objects

### Test Data & Factories

- Use factories from `tests/factories/` for creating test data
- Keep factory functions pure and deterministic
- Parameterize factories for flexibility
- Maintain test data in factories, not in conftest files

### Assertion Patterns

```python
# Good: Descriptive with context
assert result.success is True, f"Expected success, got: {result}"
assert len(members) == expected_count, "Incorrect member count"

# Less helpful
assert result == True
assert len(members) == 3
```