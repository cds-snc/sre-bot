# Testing Strategy and Structure

This document contains the new testing strategy and structure to implement within the `app/tests/` directory. It outlines the organization of test files, fixture hierarchy, factory patterns, and fake client implementations to ensure maintainable, efficient, and reliable tests.

## Directory Structure

The recommended test directory structure separates concerns clearly and provides predictable organization:

```plaintext
tests/
├── conftest.py                      # Root-level shared fixtures
├── pytest.ini                       # Pytest configuration
├── factories/                       # Test data factories
│   ├── __init__.py
│   ├── aws.py                       # AWS test data builders
│   └── google.py                    # Google test data builders
├── fixtures/                        # Reusable fake clients
│   ├── __init__.py
│   ├── aws_clients.py               # FakeClient for AWS SDK
│   └── google_clients.py            # FakeGoogleService
├── unit/                            # Pure unit tests (NEW)
│   └── modules/
│       └── groups/
│           ├── conftest.py          # Module-specific fixtures
│           ├── test_models.py
│           ├── test_schemas.py
│           ├── test_validation.py
│           └── providers/
│               ├── conftest.py      # Provider-specific fixtures
│               ├── test_base_provider.py
│               └── test_google_provider.py
├── integration/                     # Integration tests (NEW)
│   └── modules/
│       └── groups/
│           ├── conftest.py
│           ├── test_service_integration.py
│           └── test_orchestration_integration.py
└── modules/                         # Current mixed tests (MIGRATE)
    └── groups/
        ├── conftest.py
        └── test_*.py
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

### Three-Level Fixture Strategy

```plaintext
tests/conftest.py              # Level 1: Global fixtures
    ↓
tests/unit/modules/groups/conftest.py    # Level 2: Module fixtures
    ↓
tests/unit/modules/groups/providers/conftest.py  # Level 3: Feature fixtures
```

### Level 1: Root `tests/conftest.py`

Global fixtures available to all tests:

```python
# tests/conftest.py
import sys
from pathlib import Path
import pytest

# Ensure app is importable
project_root = "/workspace/app"
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture
def google_group_factory():
    """Factory for creating Google Group test data."""
    from tests.factories.google import make_google_groups
    
    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        return make_google_groups(n=n, prefix=prefix, domain=domain, as_model=as_model)
    
    return _factory


@pytest.fixture
def google_user_factory():
    """Factory for creating Google User test data."""
    from tests.factories.google import make_google_users
    
    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        return make_google_users(n=n, prefix=prefix, domain=domain, as_model=as_model)
    
    return _factory


@pytest.fixture
def google_member_factory():
    """Factory for creating Google Member test data."""
    from tests.factories.google import make_google_members
    
    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        return make_google_members(n=n, prefix=prefix, domain=domain, as_model=as_model)
    
    return _factory


@pytest.fixture
def aws_user_factory():
    """Factory for creating AWS Identity Store user test data."""
    from tests.factories.aws import make_aws_users
    
    def _factory(n=3, prefix="", domain="test.com", store_id="d-123412341234"):
        return make_aws_users(n=n, prefix=prefix, domain=domain, store_id=store_id)
    
    return _factory


@pytest.fixture
def aws_group_factory():
    """Factory for creating AWS Identity Store group test data."""
    from tests.factories.aws import make_aws_groups
    
    def _factory(n=3, prefix="", store_id="d-123412341234"):
        return make_aws_groups(n=n, prefix=prefix, store_id=store_id)
    
    return _factory


@pytest.fixture
def fake_aws_client():
    """Factory for creating FakeClient instances for AWS SDK mocking."""
    from tests.fixtures.aws_clients import FakeClient
    
    def _factory(paginated_pages=None, api_responses=None, can_paginate=None):
        return FakeClient(
            paginated_pages=paginated_pages,
            api_responses=api_responses,
            can_paginate=can_paginate
        )
    
    return _factory


@pytest.fixture
def fake_google_service():
    """Factory for creating FakeGoogleService instances."""
    from tests.fixtures.google_clients import FakeGoogleService
    
    def _factory(api_responses=None, paginated_pages=None):
        return FakeGoogleService(
            api_responses=api_responses,
            paginated_pages=paginated_pages
        )
    
    return _factory


@pytest.fixture(scope="session")
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "testdata"
```

**Scope Guidelines:**

- `function` (default): New instance per test - use for mutable state
- `class`: Shared across test class - use for test class setup
- `module`: Shared across test file - use for expensive immutable setup
- `session`: Shared across test run - use for static data, config files

### Level 2: Module `tests/unit/modules/groups/conftest.py`

Module-specific fixtures for groups functionality:

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

### Level 3: Feature `tests/unit/modules/groups/providers/conftest.py`

Feature-specific fixtures for provider tests:

```python
# tests/unit/modules/groups/providers/conftest.py
import importlib
import types
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def safe_providers_import(monkeypatch):
    """Safely import modules.groups.providers for testing.
    
    Blocks submodule imports and provides empty settings during import
    to avoid module-level registration and validation failures.
    
    Returns the imported providers module with deferred registration.
    
    Usage:
        def test_provider(safe_providers_import):
            providers = safe_providers_import
            # Import provider submodules safely
            import modules.groups.providers.google_workspace
    """
    import core.config as core_config
    from pathlib import Path
    from importlib import util
    from types import ModuleType
    import sys
    
    original_import = importlib.import_module
    
    def _stub_import(name, package=None):
        if (
            name.startswith("modules.groups.providers.")
            and name != "modules.groups.providers"
        ):
            raise ImportError("submodule imports stubbed in tests")
        return original_import(name, package)
    
    monkeypatch.setattr(importlib, "import_module", _stub_import)
    
    # Empty settings during import
    monkeypatch.setattr(
        core_config.settings,
        "groups",
        types.SimpleNamespace(
            providers={},
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_timeout_seconds=60,
            circuit_breaker_half_open_max_calls=3,
        ),
        raising=False,
    )
    
    # Clean import
    sys.modules.pop("modules.groups.providers", None)
    
    project_root = Path(__file__).resolve().parents[4]
    providers_init = project_root / "modules" / "groups" / "providers" / "__init__.py"
    
    # Lightweight package modules
    if "modules" not in sys.modules:
        pkg = ModuleType("modules")
        pkg.__path__ = [str(project_root / "modules")]
        sys.modules["modules"] = pkg
    
    if "modules.groups" not in sys.modules:
        grp_pkg = ModuleType("modules.groups")
        grp_pkg.__path__ = [str(project_root / "modules" / "groups")]
        sys.modules["modules.groups"] = grp_pkg
    
    spec = util.spec_from_file_location("modules.groups.providers", str(providers_init))
    mod = util.module_from_spec(spec)
    sys.modules["modules.groups.providers"] = mod
    spec.loader.exec_module(mod)
    
    # Deferred registration
    orig_register = getattr(mod, "register_provider")
    mod._deferred_registry = {}
    
    def _deferred_register(name: str):
        def _decorator(obj):
            mod._deferred_registry[name] = obj
            try:
                orig_register(name)(obj)
            except Exception:
                raise
            return obj
        return _decorator
    
    def _apply_deferred_registrations() -> None:
        for name, obj in list(mod._deferred_registry.items()):
            try:
                orig_register(name)(obj)
            finally:
                mod._deferred_registry.pop(name, None)
    
    monkeypatch.setattr(mod, "register_provider", _deferred_register, raising=True)
    monkeypatch.setattr(
        mod, "register_deferred_providers", _apply_deferred_registrations, raising=False
    )
    
    # Restore import
    monkeypatch.setattr(importlib, "import_module", original_import)
    
    return mod


@pytest.fixture
def mock_integration_client():
    """Mock integration client for provider tests.
    
    Pre-configured with common method stubs.
    
    Usage:
        def test_provider(mock_integration_client):
            provider.integration = mock_integration_client
            mock_integration_client.list_groups.return_value = [...]
    """
    from modules.groups.providers.base import OperationResult
    
    client = MagicMock()
    client.list_groups.return_value = OperationResult.success(data=[])
    client.get_group.return_value = OperationResult.success(data={})
    client.add_group_member.return_value = OperationResult.success(data={})
    client.remove_group_member.return_value = OperationResult.success(data={})
    client.list_group_members.return_value = OperationResult.success(data=[])
    
    return client


@pytest.fixture
def patch_provider_base_settings(monkeypatch, mock_settings_groups):
    """Patch settings import in provider base module.
    
    Simplifies provider instantiation in tests by avoiding circuit breaker setup.
    
    Usage:
        def test_provider(patch_provider_base_settings):
            # Settings already patched
            provider = GoogleWorkspaceProvider()
    """
    monkeypatch.setattr(
        "modules.groups.providers.base.settings",
        mock_settings_groups,
        raising=False
    )
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


## Migration Strategy

Legacy tests should be maintained during the transition to the new structure. New tests should adhere to the guidelines outlined above. Gradually refactor legacy tests to align with the new patterns as they are updated for new features or bug fixes.

First candidate for new tests is the groups module. All legacy tests are candidates for migration to the new structure and patterns without exception.