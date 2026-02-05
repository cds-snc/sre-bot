# Testing Standards

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
