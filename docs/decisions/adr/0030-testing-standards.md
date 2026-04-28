---
adr_id: ADR-0030
title: "Testing Standards"
status: Accepted
decision_type: Standard
tier: Tier-3
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - Platform Engineering
supersedes: []
superseded_by: []
related_records:
  - ADR-0032
related_packages: []
review_state: stale
---
# Testing Standards

## Context

Tests must be located consistently, named clearly for discoverability, and use FastAPI dependency overrides for route testing. Generic names like test_routes.py create confusion in large codebases.

## Decision

All tests live in app/tests/ with feature-prefix naming (e.g., test_groups_routes.py, test_identity_resolver.py). Use app.dependency_overrides for FastAPI route testing. Factory fixtures provide flexible test data creation.

## Consequences

- ✅ Tests are self-documenting when viewed in isolation
- ✅ No ambiguity about feature ownership
- ✅ Easy navigation and discovery
- ✅ Dependency overrides make route testing straightforward
- ⚠️ Requires consistent cleanup of dependency_overrides

---

## Test Structure

**Decision**: Tests inside `app/tests/` with unit/integration separation.

**Structure**:
```
app/tests/
├── unit/                    # Unit tests (isolated, fast)
│   ├── infrastructure/     # Tests for infrastructure/ packages
│   ├── integrations/       # Tests for integrations/ packages
│   ├── features/           # Tests for features/ packages
│   └── modules/            # Tests for modules/ (migrate legacy here)
├── integration/             # Integration tests (new structure)
├── modules/                 # ⚠️ Legacy tests (migrate to unit/modules/)
├── factories/               # Test data factories
└── fixtures/                # Fake client implementations
```

**Import Pattern**:
```python
# ✅ CORRECT - Tests inside app/ have simple imports
from infrastructure.services import get_settings
from modules.groups.core.orchestration import add_member_to_group

# ❌ WRONG - Don't manipulate sys.path
# import sys
# sys.path.insert(0, os.path.dirname(__file__))
```

**Naming Convention**: Feature-prefix test files for clarity:
```
tests/unit/packages/groups/test_groups_routes.py
tests/unit/packages/groups/test_groups_service.py
tests/unit/infrastructure/identity/test_identity_resolver.py
```

**Why Feature-Prefix**:
- Self-documenting when viewed in isolation (editors, search results)
- No confusion between test_routes.py in different features
- Clear in pytest output and tracebacks
- Easier to navigate in large codebases

**Rules**:
- ✅ All tests in `app/tests/`
- ✅ Feature-prefix: `test_<feature>_<module>.py` or `test_<package>_<module>.py`
- ✅ Current structure: `tests/modules/{feature}/`
- ✅ Future structure: `packages/groups/` → `tests/unit/packages/groups/test_groups_*.py`
- ❌ Never put tests outside `app/` directory
- ❌ No generic names like `test_routes.py` (use `test_groups_routes.py`)

---

## Dependency Override Pattern

**Decision**: Use FastAPI's `app.dependency_overrides` for testing routes.

**Implementation**:
```python
# tests/unit/api/test_groups.py
import pytest
from fastapi.testclient import TestClient
from infrastructure.services import get_settings, get_command_service
from server.main import app

@pytest.fixture
def mock_settings():
    """Mock Settings instance."""
    from infrastructure.configuration import Settings
    return Settings(
        aws=AwsSettings(AWS_REGION="us-east-1"),
        # ... other settings
    )

@pytest.fixture
def mock_command_service():
    """Mock CommandService instance."""
    from unittest.mock import MagicMock
    return MagicMock()

def test_add_member(mock_settings, mock_command_service):
    """Test add member endpoint."""
    # Override dependencies
    app.dependency_overrides[get_settings] = lambda: mock_settings
    app.dependency_overrides[get_command_service] = lambda: mock_command_service
    
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/groups/add",
            json={"group_id": "123", "member_email": "user@example.com"},
        )
        
        assert response.status_code == 200
        assert mock_command_service.execute.called
    finally:
        # CRITICAL: Always clear overrides
        app.dependency_overrides.clear()
```

**Rules**:
- ✅ Use `app.dependency_overrides` for FastAPI route tests
- ✅ Override provider functions, not services directly
- ✅ **ALWAYS** clear overrides in `finally` block
- ✅ Use fixtures for mock instances
- ❌ Never leave overrides active after test

---

## Fixture Patterns

**Decision**: Use factory-as-fixture pattern for flexibility.

**Implementation**:
```python
# tests/conftest.py
import pytest

@pytest.fixture
def make_user():
    """Factory fixture for creating User instances."""
    def _make(
        name: str = "Test User",
        email: str = "test@example.com",
        **kwargs
    ):
        return User(name=name, email=email, **kwargs)
    return _make

# Usage in tests
def test_user_creation(make_user):
    # Default user
    user1 = make_user()
    assert user1.name == "Test User"
    
    # Custom user
    user2 = make_user(name="Jane", email="jane@example.com")
    assert user2.name == "Jane"
```

**Rules**:
- ✅ Use factory-as-fixture for configurable test data
- ✅ Provide sensible defaults
- ✅ Allow overrides via parameters
- ✅ Return factory function from fixture
- ❌ Don't create fixtures for every possible configuration

---

## monkeypatch Over unittest.mock.patch

**Decision**: Prefer pytest's `monkeypatch` over `unittest.mock.patch`.

**Implementation**:
```python
# ✅ CORRECT - Use monkeypatch
def test_with_env_var(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setattr(
        "modules.groups.core.orchestration.list_groups",
        lambda: ["group1", "group2"]
    )
    # Test code...

# ❌ WRONG - Use unittest.mock.patch
from unittest.mock import patch

@patch.dict(os.environ, {"AWS_REGION": "us-west-2"})
@patch("modules.groups.core.orchestration.list_groups")
def test_with_patch(mock_list):
    # Test code...
```

**Rules**:
- ✅ Use `monkeypatch.setenv()` for environment variables
- ✅ Use `monkeypatch.setattr()` for mocking
- ✅ No manual cleanup needed
- ❌ Avoid `@patch` decorators in new tests

---

## lru_cache Teardown

**Decision**: Always clear provider `@lru_cache` singletons in test teardown alongside `dependency_overrides`.

`dependency_overrides` intercepts FastAPI's `Depends()` resolution but does **not** clear the underlying `@lru_cache`. If a provider executes before the override is set, the cached singleton persists for the remainder of the test session and contaminates subsequent tests.

```python
# tests/conftest.py
import pytest
from infrastructure.services.providers import (
    get_settings,
    get_idempotency_service,
    get_aws_clients,
    # ... add every provider used in tests
)

@pytest.fixture(autouse=True)
def clear_provider_caches():
    """Clear all @lru_cache provider singletons before and after every test."""
    get_settings.cache_clear()
    get_idempotency_service.cache_clear()
    get_aws_clients.cache_clear()
    yield
    get_settings.cache_clear()
    get_idempotency_service.cache_clear()
    get_aws_clients.cache_clear()
```

Combined with dependency overrides:

```python
def test_endpoint_with_overrides(mock_settings):
    app.dependency_overrides[get_settings] = lambda: mock_settings
    try:
        client = TestClient(app)
        response = client.get("/api/v1/example")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()  # \u274c Without this, the real singleton may survive
```

**Rules**:
- ✅ Add every `@lru_cache` provider to the `clear_provider_caches` autouse fixture
- ✅ Clear both before and after each test (pre-clear eliminates state from non-test imports)
- ✅ Clear `dependency_overrides` and provider caches together in `finally` blocks
- ❌ Never rely on `dependency_overrides` alone when providers may already be cached

---

## Async Testing Pattern

**Decision**: Use `httpx.AsyncClient` with `anyio` for async route handlers and async services.

`TestClient` wraps the ASGI app in a synchronous thread and can mask async-specific bugs (cancellation, `contextvars` propagation, task leaks). Use `AsyncClient` to test async paths faithfully.

**Setup** (`pytest.ini` or `pyproject.toml`):
```ini
[pytest]
anyio_mode = auto
```

**Async test fixture**:
```python
# tests/conftest.py
import pytest
import httpx
from httpx import AsyncClient
from asgi_lifespan import LifespanManager
from server.main import app

@pytest.fixture
async def async_client():
    """Async HTTP client running full ASGI lifespan."""
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
```

**Usage**:
```python
import pytest

@pytest.mark.anyio
async def test_async_endpoint(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/groups/add",
        json={"group_id": "123", "member_email": "user@example.com"},
    )
    assert response.status_code == 200
```

**When to use each client**:

| Scenario | Use |
|---|---|
| Sync route handlers, simple integration tests | `TestClient` |
| Async route handlers, cancellation, `contextvars` propagation | `AsyncClient` + `anyio` |
| Background task or scheduler behaviour | `AsyncClient` + `anyio` |

**Rules**:
- ✅ Use `anyio_mode = auto` in `pytest.ini` to avoid per-test `@pytest.mark.anyio`
- ✅ Wrap app in `LifespanManager` so startup/shutdown hooks run in async tests
- ✅ Use `async_client` fixture pattern for reuse across test modules
- ✅ Add `httpx` and `anyio` and `asgi-lifespan` to `requirements_dev.txt`
- ❌ Do not use `TestClient` to test async routes that use `contextvars` or task groups
