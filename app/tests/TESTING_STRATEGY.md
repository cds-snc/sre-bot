# Testing Strategy and Structure

This document defines the testing strategy for the `app/tests/` directory, aligned with **official pytest best practices** (pytest 9.x) and Python conventions.

---

## Migration Guide: Legacy to New Structure

> **Current State**: Tests are in `/workspace/app/tests/` with a hybrid structure (legacy flat + new `unit/`/`integration/` directories).

### Why Keep Tests Inside `app/`?

For this project, **keeping tests inside `app/tests/`** is the recommended approach:

1. **Simpler imports**: No need to configure `PYTHONPATH` or `--import-mode`
2. **Single working directory**: All commands run from `/workspace/app`
3. **Existing infrastructure works**: Current `pytest.ini`, `conftest.py`, and CI all assume `app/tests/`
4. **Lower risk**: Moving tests outside `app/` can break imports in subtle ways

### Migration Strategy: In-Place Reorganization

Instead of moving the entire `tests/` directory, **reorganize in place**:

```plaintext
# Current hybrid structure
tests/
├── unit/                    # ✅ NEW structure (keep expanding)
│   ├── infrastructure/
│   ├── integrations/        # Unit tests for integration clients
│   └── modules/
├── integration/             # ✅ NEW structure (keep expanding)
│   ├── infrastructure/
│   └── modules/
├── modules/                 # ⚠️ LEGACY (migrate to unit/modules/)
├── integrations/            # ⚠️ LEGACY (migrate to unit/integrations/)
├── api/                     # ⚠️ LEGACY (migrate to unit/api/ or integration/)
├── core/                    # ⚠️ LEGACY (migrate to unit/core/)
├── factories/               # ✅ Keep (shared across all tests)
├── fixtures/                # ✅ Keep (shared across all tests)
└── testdata/                # ✅ Keep (shared across all tests)
```

### Step-by-Step Migration

#### Phase 1: Mark Legacy Tests (No Breaking Changes)

Add `@pytest.mark.legacy` marker to track migration progress. The marker is already in `pytest.ini`.

**Run only legacy tests**: `pytest -m legacy`
**Run only new tests**: `pytest -m "not legacy"`

#### Phase 2: Migrate One Module at a Time

1. **Copy** the test file to the new location:
   ```bash
   mkdir -p tests/unit/modules/incident
   cp tests/modules/incident/test_incident.py tests/unit/modules/incident/
   ```

2. **Update imports** if needed (most should work as-is since we use absolute imports)

3. **Add proper markers** (`@pytest.mark.unit` or `@pytest.mark.integration`)

4. **Run both** to verify identical behavior:
   ```bash
   pytest tests/modules/incident/test_incident.py -v
   pytest tests/unit/modules/incident/test_incident.py -v
   ```

5. **Delete the legacy file** once migrated and CI passes

#### Phase 3: Refactor to New Patterns (Optional)

When migrating, consider updating to new patterns:

```python
# BEFORE (legacy pattern with @patch)
from unittest.mock import patch

@patch("modules.incident.incident.list_folders")
def test_list_folders(mock_list):
    mock_list.return_value = [{"id": "1"}]
    ...

# AFTER (new pattern with monkeypatch)
def test_list_folders(monkeypatch):
    monkeypatch.setattr(
        "modules.incident.incident.list_folders",
        lambda: [{"id": "1"}]
    )
    ...
```

### Migration Tracking

Track progress with pytest markers:

```bash
# Count legacy vs new tests
pytest --collect-only -q -m legacy 2>/dev/null | tail -1
pytest --collect-only -q -m unit 2>/dev/null | tail -1
pytest --collect-only -q -m integration 2>/dev/null | tail -1
```

### Directory Mapping

| Legacy Location | New Location | Type |
|-----------------|--------------|------|
| `tests/modules/<mod>/test_*.py` | `tests/unit/modules/<mod>/` | unit |
| `tests/integrations/<int>/test_*.py` | `tests/unit/integrations/<int>/` | unit |
| `tests/api/test_*.py` | `tests/unit/api/` or `tests/integration/api/` | depends |
| `tests/core/test_*.py` | `tests/unit/core/` | unit |
| `tests/jobs/test_*.py` | `tests/unit/jobs/` | unit |

### Files to Keep in Place

These directories are shared infrastructure and should NOT be moved:

- `tests/conftest.py` - Root fixtures
- `tests/factories/` - Test data factories  
- `tests/fixtures/` - Fake client implementations
- `tests/testdata/` - Static test data files

---

## Core Principles

Based on [pytest good practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html):

1. **Tests in dedicated directory** - Tests in `app/tests/` separate from source modules
   > *Note*: pytest recommends "tests outside application code". We keep tests inside `app/` for simpler imports since all commands run from `/workspace/app`. This is a practical tradeoff documented in the Migration Guide above.
2. **importlib import mode** - Recommended for new projects, avoids `sys.path` manipulation
3. **Strict mode enabled** - Catch configuration errors early
4. **Fixtures via conftest.py** - Hierarchical fixture sharing
5. **Factory-as-fixture pattern** - Factories return callables for flexible test data
6. **Yield fixtures** - Preferred for setup/teardown (over `addfinalizer`)

## Environment Variables

All environment variable loading is centralized in `infrastructure.configuration.settings` and accessed via the services façade `from infrastructure.services import get_settings`. In tests (or infra internals when clearing `@lru_cache`), you can import the provider directly `from infrastructure.services.providers import get_settings`. Tests should:
- **NOT** load `.env` files directly
- Access configuration via `settings` object retrieved from `get_settings()`
- Use pytest.ini `env` section for test-specific overrides
- Mock settings via fixtures when isolation is needed

### ⚠️ Anti-Pattern: Settings Import From Configuration

**Module-level `settings = get_settings()` is CORRECT in production code** per our architecture standards:

```python
# ✅ CORRECT - Standard pattern for infrastructure/module code
from infrastructure.services import get_settings

logger = structlog.get_logger()
settings = get_settings()  # Cached singleton via @lru_cache

def some_function():
    return settings.aws.AWS_REGION
```

**Why module-level `get_settings()` is correct:**
- `@lru_cache` ensures ONE Settings instance per process (singleton pattern)
- Each ECS task gets its own cached singleton (supports horizontal scaling)
- Consistent with infrastructure layer requirements

**However, NEVER bypass the singleton by importing `settings` directly:**

```python
# ❌ BAD - Creates SECOND Settings instance, breaks singleton!
from infrastructure.configuration import settings  

def some_function():
    return settings.aws.AWS_REGION
```

**Why `from infrastructure.configuration import settings` is problematic:**
- Creates a separate Settings() instance at module import time
- Breaks the singleton pattern - now have TWO instances in the process
- Violates architectural requirement to use `get_settings()` from services
- Cannot be properly mocked without complex import manipulation

**✅ CORRECT patterns:**

```python
# 1. For route handlers: Use dependency injection
from infrastructure.services import SettingsDep

@router.get("/config")
def get_config(settings: SettingsDep):
    return {"region": settings.aws.AWS_REGION}

# 2. For infrastructure/module code: Module-level get_settings() call
from infrastructure.services import get_settings

logger = structlog.get_logger()
settings = get_settings()  # Standard pattern

def setup_client():
    return Client(region=settings.aws.AWS_REGION)

# 3. For functions with explicit dependencies: Accept as parameter
from infrastructure.configuration import Settings  # Type hint only

def setup_client(config: Settings):
    return Client(region=config.aws.AWS_REGION)
```

**In tests**, handle `@lru_cache` by clearing cache and patching both function and variable:

```python
from infrastructure.services.providers import get_settings

def test_something(monkeypatch):
    # Clear @lru_cache to allow our mock
    get_settings.cache_clear()
    
    mock_settings = MagicMock()
    mock_settings.aws.AWS_REGION = "us-west-2"
    
    # Patch the function
    monkeypatch.setattr(
        "your.module.get_settings",
        lambda: mock_settings
    )
    # Patch the module-level variable
    monkeypatch.setattr(
        "your.module.settings",
        mock_settings
    )
```

## Pytest Configuration

All pytest configuration is centralized in `/workspace/app/pytest.ini`.

### Key Settings

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
norecursedirs = tests/smoke

# Strict mode (pytest 9.0+) - recommended for all projects
strict_markers = true
strict_config = true

# Import mode - use importlib for cleaner imports
addopts = --import-mode=importlib -ra --strict-markers --showlocals --tb=short

# Markers
markers =
    unit: Pure unit tests with no external dependencies (<50ms)
    integration: Integration tests combining multiple components (<500ms)
    slow: Tests that take >1 second
    external: Tests requiring external services (skip in CI)
```

### Test Discovery Rules

Per [pytest conventions](https://docs.pytest.org/en/stable/explanation/goodpractices.html#conventions-for-python-test-discovery):

- **Directories**: Recurse into all directories except `norecursedirs`
- **Files**: Match `test_*.py` or `*_test.py` patterns
- **Functions**: Match `test_*` prefix (outside or inside `Test*` classes)
- **Classes**: Match `Test*` prefix (no `__init__` method)

### Markers

| Marker | Description | Target Time |
|--------|-------------|-------------|
| `@pytest.mark.unit` | Pure unit tests, mocked dependencies | <50ms |
| `@pytest.mark.integration` | Multi-component tests, stubbed services | <500ms |
| `@pytest.mark.slow` | Expensive tests (skip in quick runs) | >1s |
| `@pytest.mark.external` | Requires external services | N/A |

### Running Tests

```bash
# All tests (from /workspace/app)
pytest

# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Exclude slow tests
pytest -m "not slow"

# Specific module
pytest tests/unit/modules/groups/

# Specific test class
pytest tests/unit/modules/groups/test_models.py::TestNormalizedMember

# With coverage
pytest --cov=modules.groups --cov-report=html

# Verbose with locals on failure
pytest -v --showlocals
```

## Directory Structure

Following pytest's recommended "tests outside application code" layout:

```plaintext
app/                                 # Application source
tests/                               # Test suite (separate from source)
├── conftest.py                      # Root fixtures (Level 1)
├── factories/                       # Test data factories (factory-as-fixture)
│   ├── __init__.py
│   ├── aws.py                       # AWS test data builders
│   ├── commands.py                  # Command framework data builders
│   ├── google.py                    # Google test data builders
│   ├── groups_commands.py           # Groups command data builders
│   └── i18n.py                      # i18n test data builders
├── fixtures/                        # Reusable fake client implementations
│   ├── __init__.py
│   ├── aws_clients.py               # FakeClient for AWS SDK
│   └── google_clients.py            # FakeGoogleService
├── testdata/                        # Static test data files (JSON, etc.)
├── unit/                            # Pure unit tests
│   ├── __init__.py
│   ├── infrastructure/              # Infrastructure component tests
│   │   ├── conftest.py              # Infrastructure fixtures (Level 2)
│   │   ├── commands/
│   │   │   ├── conftest.py          # Commands fixtures (Level 3)
│   │   │   ├── providers/
│   │   │   │   ├── conftest.py      # Provider fixtures (Level 4)
│   │   │   │   ├── test_base.py
│   │   │   │   └── test_slack.py
│   │   │   ├── responses/
│   │   │   │   ├── test_models.py
│   │   │   │   └── test_slack_formatter.py
│   │   │   ├── test_context.py
│   │   │   ├── test_parser.py
│   │   │   └── test_registry.py
│   │   ├── i18n/
│   │   │   ├── conftest.py
│   │   │   ├── test_loader.py
│   │   │   └── test_translator.py
│   │   └── resilience/
│   │       ├── test_circuit_breaker.py
│   │       └── test_operations_result.py
│   └── modules/                     # Feature module tests
│       ├── groups/
│       │   ├── conftest.py          # Groups fixtures (Level 2)
│       │   ├── commands/
│       │   │   └── test_registry.py
│       │   ├── providers/
│       │   │   ├── conftest.py      # Provider fixtures (Level 3)
│       │   │   ├── test_aws_identity_center.py
│       │   │   ├── test_base_provider.py
│       │   │   └── test_google_workspace_provider.py
│       │   ├── test_models.py
│       │   ├── test_orchestration.py
│       │   ├── test_schemas.py
│       │   └── test_validation.py
│       └── sre/
│           ├── conftest.py
│           └── test_webhook_helper.py
├── integration/                     # Integration tests
│   ├── __init__.py
│   ├── conftest.py                  # Integration fixtures (boundary mocks)
│   ├── infrastructure/
│   │   └── commands/
│   │       ├── test_provider_integration.py
│   │       └── test_router_integration.py
│   └── modules/
│       └── groups/
│           ├── conftest.py
│           ├── test_orchestration_integration.py
│           └── test_service_integration.py
└── smoke/                           # Smoke tests (require credentials)
    └── (excluded from default run)
```

### Directory Purpose

| Directory | Purpose | Characteristics |
|-----------|---------|-----------------|
| `tests/unit/` | Pure unit tests | Mocked deps, <50ms, no I/O |
| `tests/integration/` | Component integration | Stubbed services, <500ms |
| `tests/factories/` | Test data factory functions | Pure, deterministic, reusable |
| `tests/fixtures/` | Fake client implementations | Configurable mocks, stateful |
| `tests/testdata/` | Static test data | JSON, fixtures, immutable |
| `tests/smoke/` | Live service tests | Requires credentials |

## Fixture Architecture

### conftest.py: Sharing Fixtures Across Files

Per [pytest fixture reference](https://docs.pytest.org/en/stable/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files):

> Fixtures defined in a `conftest.py` can be used by any test in that package without needing to import them (pytest will automatically discover them).

### Hierarchical Fixture Scopes

```plaintext
tests/conftest.py                           # Level 1: Global (session/module scope)
    ↓
tests/unit/modules/<module>/conftest.py     # Level 2: Module-specific fixtures
    ↓
tests/unit/modules/<module>/<feature>/conftest.py  # Level 3: Feature fixtures
```

**Scope Selection Rules** (per pytest docs):

| Scope | Lifetime | Use Case |
|-------|----------|----------|
| `function` | Per test (default) | Mutable state, isolated tests |
| `class` | Per test class | Shared setup within class |
| `module` | Per test file | Expensive setup, immutable data |
| `package` | Per test directory | Shared across subpackages |
| `session` | Entire test run | Static config, DB connections |

**Instantiation Order**:
1. Higher-scoped fixtures execute first (`session` → `package` → `module` → `class` → `function`)
2. Within same scope, dependencies execute first
3. Autouse fixtures execute before non-autouse in same scope

### Fixture Scoping Strategy

**Default scope: `function`** (recommended for most fixtures)

Per [pytest documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html#scope-sharing-fixtures-across-classes-modules-packages-or-session), fixtures can have different scopes:

| Scope | Lifetime | Use When | Example |
|-------|----------|----------|----------|
| `function` | Per test (default) | Most cases - ensures test isolation | Mock objects, test data |
| `class` | Per test class | Shared setup within class | Class-level config |
| `module` | Per test file | Expensive setup, **immutable** data | Database connections |
| `package` | Per test directory | Shared across subpackages | Rarely needed |
| `session` | Entire test run | **Very rare** - static, global config | Test suite bootstrap |

**Guidelines:**

1. **Default to `function` scope** unless you have a specific reason
2. **Broader scopes require immutability** - tests should not modify shared fixtures
3. **Beware of @lru_cache** - Settings fixtures must handle cached functions
4. **Test isolation > Performance** - only optimize after measuring

**Settings Fixture Scoping:**

```python
# ✅ Function scope (RECOMMENDED) - fresh mock per test
@pytest.fixture
def mock_settings(monkeypatch):
    # Each test gets independent settings mock
    # No state leakage between tests
    ...

# ⚠️ Module scope - use cautiously
@pytest.fixture(scope="module")
def integration_settings():
    # Shared across all tests in file
    # Only use if settings truly never change
    # Risk: tests may interfere with each other
    ...

# ❌ Session scope - avoid for settings
# Settings should be mockable per-test
```

**When to use broader scopes:**

```python
# ✅ Good use of module scope - expensive, immutable setup
@pytest.fixture(scope="module")
def database_schema():
    """Create DB schema once per test module."""
    conn = create_connection()
    conn.execute("CREATE TABLE...")
    yield conn
    conn.execute("DROP TABLE...")

# ❌ Bad use of module scope - mutable state
@pytest.fixture(scope="module")
def user_data():
    """Don't share mutable data across tests!"""
    return {"count": 0}  # Tests will modify this!
```

### Fixture Patterns

#### ⚠️ Anti-Pattern: Inline Mock Creation

**❌ DO NOT create mock objects inline in test methods:**

```python
# BAD - Creates mock in every test method
def test_something(retry_config_factory):
    """Anti-pattern: SimpleNamespace created inline."""
    mock_settings = SimpleNamespace(retry=SimpleNamespace(backend="memory"))
    store = create_retry_store(retry_config_factory(), mock_settings)
    assert isinstance(store, InMemoryRetryStore)
```

**Why this is problematic:**
- Code duplication across multiple tests
- Harder to maintain when settings structure changes
- Test logic mixed with test data setup
- Inconsistent with other test modules

**✅ DO define fixtures in conftest.py:**

```python
# conftest.py
@pytest.fixture
def mock_settings():
    """Create mock settings for tests."""
    settings = MagicMock()
    settings.retry.backend = "memory"
    settings.retry.batch_size = 10
    return settings

# In test file
def test_something(retry_config_factory, mock_settings):
    """Cleaner: fixture from conftest."""
    store = create_retry_store(retry_config_factory(), mock_settings)
    assert isinstance(store, InMemoryRetryStore)
```

**Benefits:**
- DRY principle - single source of truth
- Consistent across all tests in module/package
- Uses `MagicMock` for flexibility and IDE support
- Easier to update when mocking strategy changes
- Clear separation of concerns (data setup vs test logic)

**Guideline:** Any mock object used by multiple tests should be defined as a fixture in `conftest.py`, not created inline.

#### 1. Yield Fixtures (Recommended for Teardown)

Per [pytest docs](https://docs.pytest.org/en/stable/how-to/fixtures.html#yield-fixtures-recommended):

```python
@pytest.fixture
def database_connection():
    """Yield fixture with setup and teardown."""
    conn = create_connection()
    yield conn  # Test runs here
    conn.close()  # Teardown after test
```

#### 2. Factory-as-Fixture Pattern

Per [pytest docs](https://docs.pytest.org/en/stable/how-to/fixtures.html#factories-as-fixtures):

```python
@pytest.fixture
def make_customer_record():
    """Factory fixture returns a callable."""
    created_records = []

    def _make_customer_record(name: str):
        record = Customer(name=name)
        created_records.append(record)
        return record

    yield _make_customer_record
    
    # Cleanup all created records
    for record in created_records:
        record.destroy()
```

#### 3. Autouse Fixtures

Use sparingly for cross-cutting concerns:

```python
@pytest.fixture(autouse=True)
def suppress_logging():
    """Applied to all tests in this scope automatically."""
    import logging
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)
```

### Level 1: Root Fixtures (`tests/conftest.py`)

Global fixtures available to all tests:

```python
# tests/conftest.py

import sys
import pytest
from unittest.mock import MagicMock

from infrastructure.configuration import Settings

# ─────────────────────────────────────────────────────────────────────────────
# SESSION SETUP (autouse)
# ─────────────────────────────────────────────────────────────────────────────

def pytest_configure(config):
    """Mock Slack App before any imports to prevent auth errors."""
    sys.modules["integrations.slack.app"] = MagicMock()


@pytest.fixture(autouse=True, scope="session")
def suppress_structlog_output():
    """Suppress application logging for clean test output."""
    import structlog
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(50)  # CRITICAL only
    )
    yield


# ─────────────────────────────────────────────────────────────────────────────
# FACTORY FIXTURES (function scope)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def google_group_factory():
    """Factory for creating Google Group test data."""
    from tests.factories.google import make_google_groups
    return make_google_groups


@pytest.fixture
def google_user_factory():
    """Factory for creating Google User test data."""
    from tests.factories.google import make_google_users
    return make_google_users


@pytest.fixture
def aws_user_factory():
    """Factory for creating AWS Identity Center user test data."""
    from tests.factories.aws import make_aws_users
    return make_aws_users


# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS FACTORY (Level 1 - DRY principle)
# ─────────────────────────────────────────────────────────────────────────────
# NOTE: Settings use factory-as-fixture pattern to follow DRY principle
# and avoid duplication across test packages. See Fixture Architecture
# section for details on hierarchical fixture design.

@pytest.fixture
def make_mock_settings():
    """Factory for creating mock settings with package-specific overrides.

    Uses the factory-as-fixture pattern to eliminate code duplication
    across different test packages. Each package can override specific
    settings via keyword arguments without recreating the entire mock.

    This follows the same factory-as-fixture pattern recommended for
    test data factories (google_groups, aws_users, etc.) but applied
    to configuration objects.

    **Why factory pattern for settings?**
    - DRY: Single source of truth for default settings
    - Flexible: Each package sets only the fields it needs
    - Hierarchical: Parent conftest provides base, child adds specifics
    - Composable: Easy to extend without duplication

    Usage at each level:

    ```python
    # Level 1 (root conftest.py)
    @pytest.fixture
    def make_mock_settings():
        def _factory(**overrides):
            settings = MagicMock()
            settings.aws.AWS_REGION = "us-east-1"  # Defaults
            # Apply overrides...
            return settings
        return _factory

    # Level 2 (tests/integration/conftest.py)
    @pytest.fixture
    def mock_settings(make_mock_settings):
        return make_mock_settings(
            **{
                'idempotency.IDEMPOTENCY_TTL_SECONDS': 3600,
                'commands.providers': {},
            }
        )

    # Level 3 (tests/integration/infrastructure/commands/conftest.py)
    @pytest.fixture
    def mock_settings(make_mock_settings):
        return make_mock_settings(
            **{
                'slack.SLACK_TOKEN': 'xoxb-test-token',
                'commands.providers': {},
            }
        )
    ```

    Args:
        **overrides: Package-specific settings to override defaults

    Returns:
        MagicMock: Settings mock with applied overrides
    """
    from unittest.mock import MagicMock

    def _factory(**overrides):
        """Create mock settings with provided overrides."""
        settings = MagicMock()
        
        # Set common defaults for all packages
        settings.aws.AWS_REGION = "us-east-1"
        
        # Apply package-specific overrides
        for key, value in overrides.items():
            if '.' in key:
                # Handle nested attributes: 'slack.SLACK_TOKEN' -> settings.slack.SLACK_TOKEN
                parts = key.split('.')
                obj = settings
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)
            else:
                setattr(settings, key, value)
        
        return settings

    return _factory


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_settings_real(monkeypatch):
    """Alternative: Real Settings instance with environment variable overrides.
    
    Use this when you need Pydantic validation and type safety.
    Most tests should use the MagicMock approach via make_mock_settings.

    Usage:
        def test_something(mock_settings_real):
            settings = mock_settings_real(
                aws__AWS_REGION="us-west-2",
                server__LOG_LEVEL="DEBUG"
            )
            # settings is a real Settings instance with validation
    
    Args:
        monkeypatch: pytest's monkeypatch fixture
    
    Returns:
        Callable that creates and installs a real Settings instance
    """
    def _mock_settings_real(**overrides):
        # Create a Settings mock with spec for type safety
        mock = MagicMock()
        
        # Apply overrides using double-underscore for nested attributes
        # Example: aws__AWS_REGION -> mock.aws.AWS_REGION = "us-west-2"
        for key, value in overrides.items():
            parts = key.split("__")
            target = mock
            
            # Navigate to nested attribute
            for part in parts[:-1]:
                if not hasattr(target, part):
                    setattr(target, part, MagicMock())
                target = getattr(target, part)
            
            # Set the final value
            setattr(target, parts[-1], value)
        
        # CRITICAL: Replace get_settings() to handle @lru_cache
        # We replace the entire function, not just the return value
        monkeypatch.setattr(
            "infrastructure.services.providers.get_settings",
            lambda: mock,
            raising=False,
        )
        
        return mock
    
    return _mock_settings_real


@pytest.fixture
def mock_settings_real(monkeypatch):
    """Alternative: Use real Settings instance with environment variable overrides.
    
    This fixture creates actual Settings objects for maximum realism.
    Use when you need full Pydantic validation or complex nested structures.
    
    Usage:
        def test_with_validation(mock_settings_real):
            settings = mock_settings_real(
                AWS_REGION="us-east-1",
                SLACK_TOKEN="xoxb-test-token"
            )
            # settings is a real Settings() instance
    
    Args:
        monkeypatch: pytest's monkeypatch fixture
    
    Returns:
        Callable that creates real Settings with env overrides
    """
    def _mock_settings(**env_overrides):
        # Set environment variables temporarily
        for key, value in env_overrides.items():
            monkeypatch.setenv(key, str(value))
        
        # Create real Settings instance (will load from env)
        settings = Settings()
        
        # Replace get_settings() to return this instance
        monkeypatch.setattr(
            "infrastructure.services.providers.get_settings",
            lambda: settings,
            raising=False,
        )
        
        return settings
    
    return _mock_settings
```

### Settings Mocking: Real vs Mock

**When to use each approach:**

| Approach | Use When | Pros | Cons |
|----------|----------|------|------|
| **MagicMock (default)** | Most unit tests | Simple, flexible, fast | No validation, spec drift |
| **Real Settings** | Integration tests, validation tests | Type safety, Pydantic validation | Slower, requires env setup |

**Primary pattern: MagicMock with spec**

```python
def test_with_mock(mock_settings):
    """Fast, isolated unit test."""
    settings = mock_settings(
        aws__AWS_REGION="us-east-1",
        retry__enabled=True
    )
    # Quick mocking for unit tests
    assert settings.aws.AWS_REGION == "us-east-1"
```

**Benefits:**
- Fast test execution
- Easy to set up partial mocks
- Fine-grained control over behavior
- No file I/O or environment pollution

**Alternative: Real Settings with env overrides**

```python
def test_with_real_settings(mock_settings_real):
    """Integration test with full validation."""
    settings = mock_settings_real(
        AWS_REGION="us-west-2",
        SLACK_TOKEN="xoxb-test"
    )
    # Real Settings instance with Pydantic validation
    assert isinstance(settings.aws.AWS_REGION, str)
```

**Benefits:**
- Catches Pydantic validation errors
- Verifies actual Settings schema
- IDE autocomplete works
- Tests closer to production

**Use real Settings when:**
- Testing settings initialization logic
- Verifying Pydantic validators
- Integration tests with real components
- You need to catch schema mismatches

**Use MagicMock when:**
- Pure unit tests with stubbed dependencies
- Need to mock methods (not just data)
- Speed is critical (thousands of tests)
- Testing edge cases that are hard to configure via env

### FastAPI Dependency Override Pattern

For testing FastAPI routes that use `SettingsDep`, override the dependency:

```python
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from infrastructure.services.providers import get_settings

def test_endpoint_with_settings_override(app):
    """Test FastAPI route with custom settings."""
    # Create mock settings
    mock_settings = MagicMock()
    mock_settings.aws.AWS_REGION = "us-east-1"
    
    # Override the dependency
    app.dependency_overrides[get_settings] = lambda: mock_settings
    
    try:
        client = TestClient(app)
        response = client.get("/api/v1/config")
        assert response.status_code == 200
        assert "us-east-1" in response.json()["region"]
    finally:
        # Clean up - critical for test isolation!
        app.dependency_overrides.clear()
```

**Important:** Always clear `app.dependency_overrides` in cleanup to prevent test pollution.

Note: Importing `get_settings` from `infrastructure.services` also works; both references point to the same provider function.

### Level 2: Module Fixtures

Module-specific fixtures in `tests/unit/modules/<module>/conftest.py`:

```python
# tests/unit/modules/groups/conftest.py

import pytest
from unittest.mock import MagicMock

from modules.groups.models import NormalizedMember, NormalizedGroup

# ─────────────────────────────────────────────────────────────────────────────
# MOCK PROVIDERS
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_primary_provider():
    """Mock primary group provider."""
    provider = MagicMock()
    provider.name = "google"
    provider.is_primary = True
    return provider


# ─────────────────────────────────────────────────────────────────────────────
# DOMAIN MODEL FACTORIES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def normalized_member_factory():
    """Factory for creating NormalizedMember instances."""
    
    def _factory(
        email: str = "test@example.com",
        id: str = "user-1",
        role: str = "member",
        **kwargs
    ) -> NormalizedMember:
        return NormalizedMember(email=email, id=id, role=role, **kwargs)
    
    return _factory


@pytest.fixture
def normalized_group_factory():
    """Factory for creating NormalizedGroup instances."""
    def _factory(
        id: str = "group-1",
        name: str = "Test Group",
        provider: str = "test",
        **kwargs
    ) -> NormalizedGroup:
        return NormalizedGroup(id=id, name=name, provider=provider, **kwargs)
    
    return _factory
```

### Level 3: Feature Fixtures

Feature-specific fixtures in nested conftest files:

```python
# tests/unit/modules/groups/providers/conftest.py

import pytest
from unittest.mock import MagicMock

# ─────────────────────────────────────────────────────────────────────────────
# MOCK CLIENTS
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_google_directory_client():
    """Mock Google Directory API client."""
    client = MagicMock()
    client.groups.return_value.list.return_value.execute.return_value = {
        "groups": []
    }
    return client


@pytest.fixture
def sample_google_group_data():
    """Sample Google group response data."""
    return {
        "id": "group-123",
        "email": "test-group@example.com",
        "name": "Test Group",
        "directMembersCount": 5,
    }
```

## Factory Pattern

### Factory-as-Fixture Implementation

Per [pytest documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html#factories-as-fixtures), factories return callables:

```python
# tests/factories/google.py
"""Google Workspace test data factories.

These are pure functions that create test data deterministically.
"""

from typing import List, Dict, Any

from integrations.google_workspace.schemas import Group, User


def make_google_groups(n: int = 3, prefix: str = "", domain: str = "test.com"):
    """Create test Google Group data.
    
    Args:
        n: Number of groups to create
        prefix: String prefix for IDs and names
        domain: Email domain
    
    Returns:
        List of Group dicts (serializable)
    """
    return [
        {
            "id": f"{prefix}group-id-{i+1}",
            "name": f"{prefix}group-name-{i+1}",
            "email": f"{prefix}group-name-{i+1}@{domain}",
            "directMembersCount": i + 1,
        }
        for i in range(n)
    ]


def make_google_users(n: int = 3, prefix: str = "", domain: str = "test.com"):
    """Create test Google User data."""
    return [
        {
            "id": f"{prefix}user-id-{i+1}",
            "primaryEmail": f"{prefix}user-{i+1}@{domain}",
            "name": {
                "givenName": f"Given{i+1}",
                "familyName": f"Family{i+1}",
                "fullName": f"Given{i+1} Family{i+1}",
            },
        }
        for i in range(n)
    ]
```

### Using Factory Fixtures

```python
def test_list_groups_returns_normalized(google_group_factory):
    """Test using factory fixture from root conftest."""
    # Factory is a callable - invoke with parameters
    raw_groups = google_group_factory(n=5, prefix="test-")
    
    assert len(raw_groups) == 5
    assert raw_groups[0]["name"] == "test-group-name-1"


def test_with_multiple_factories(google_group_factory, google_user_factory):
    """Combine multiple factories for complex scenarios."""
    groups = google_group_factory(n=2)
    users = google_user_factory(n=3, domain="example.com")
    
    assert len(groups) == 2
    assert all(u["primaryEmail"].endswith("@example.com") for u in users)
```

## Integration Test Fixtures

### Integration Test Architecture

Integration tests mock **system boundaries** while allowing real component interaction:

```plaintext
tests/integration/conftest.py                    # System boundary mocks (autouse)
    ↓
tests/integration/modules/<module>/conftest.py   # Module-specific mocks
    ↓
tests/integration/<area>/<component>/conftest.py # Component-specific setup
```

### Root Integration Fixtures (`tests/integration/conftest.py`)

Autouse fixtures that mock external systems:

```python
# tests/integration/conftest.py

import pytest
from unittest.mock import MagicMock, patch

# ─────────────────────────────────────────────────────────────────────────────
# BOUNDARY MOCKS (autouse)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_dynamodb_audit(monkeypatch):
    """Prevent actual DynamoDB writes during all integration tests."""
    monkeypatch.setattr(
        "infrastructure.persistence.dynamodb.audit.write_audit_event",
        MagicMock(return_value=None)
    )


@pytest.fixture(autouse=True)
def mock_sentinel_client(monkeypatch):
    """Prevent actual Sentinel calls during all integration tests."""
    monkeypatch.setattr(
        "integrations.sentinel.client.log_to_sentinel",
        MagicMock(return_value=None)
    )
    monkeypatch.setattr(
        "integrations.sentinel.client.log_audit_event",
        MagicMock(return_value=None)
    )
```

### Module Integration Fixtures

Module-specific integration fixtures:

```python
# tests/integration/modules/groups/conftest.py

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_orchestration():
    """Configurable mock orchestration layer."""
    mock = MagicMock()
    mock.add_member.return_value = {"success": True}
    mock.remove_member.return_value = {"success": True}
    return mock


@pytest.fixture
def mock_event_dispatch():
    """Captures dispatched events for verification."""
    dispatched = []
    
    def _dispatch(event_type, payload):
        dispatched.append({"type": event_type, "payload": payload})
    
    _dispatch.get_dispatched = lambda: list(dispatched)
    _dispatch.clear = lambda: dispatched.clear()
    
    return _dispatch
```

## Fake Client Pattern

### FakeClient for External SDKs

Fake clients simulate external service behavior for testing:

```python
# tests/fixtures/aws_clients.py
"""Fake AWS client implementations for testing."""

from typing import Any, Callable, List


class FakePaginator:
    """Simulates boto3 paginator."""
    
    def __init__(self, pages: List[dict]):
        self._pages = pages
    
    def paginate(self, **kwargs):
        yield from self._pages


class FakeAWSClient:
    """Fake boto3 client for testing.
    
    Usage:
        client = FakeAWSClient(
            api_responses={
                "describe_user": {"UserId": "u-1"},
                "create_user": lambda **kw: {"UserId": f"new-{kw['UserName']}"},
            },
            paginated_pages=[
                {"Users": [{"UserId": "u-1"}], "NextToken": "tok"},
                {"Users": [{"UserId": "u-2"}]},
            ]
        )
    """
    
    def __init__(
        self,
        paginated_pages: List[dict] = None,
        api_responses: dict = None,
    ):
        self._paginated_pages = paginated_pages or []
        self._api_responses = api_responses or {}
    
    def get_paginator(self, operation_name: str):
        return FakePaginator(self._paginated_pages)
    
    def __getattr__(self, name: str) -> Callable:
        if name not in self._api_responses:
            raise AttributeError(f"No mock for {name}")
        
        response = self._api_responses[name]
        if callable(response):
            return response
        return lambda **kwargs: response
```

### Using Fake Clients

```python
def test_list_users_with_pagination(monkeypatch):
    """Test AWS integration using FakeClient."""
    from tests.fixtures.aws_clients import FakeAWSClient
    
    client = FakeAWSClient(
        paginated_pages=[
            {"Users": [{"UserId": "u-1"}], "NextToken": "t1"},
            {"Users": [{"UserId": "u-2"}]},
        ]
    )
    
    monkeypatch.setattr(
        "integrations.aws.identity_store.get_client",
        lambda service: client
    )
    
    from integrations.aws import identity_store
    users = list(identity_store.list_users())
    
    assert len(users) == 2
```

## Test Organization

### Import Conventions

Follow PEP 8 import order:

```python
# 1. Standard library
import json
from typing import Dict, List

# 2. Third-party packages
import pytest
from pydantic import ValidationError

# 3. Local application
from infrastructure.operations import OperationResult
from modules.groups.models import NormalizedMember
```

**Import at module level**, not inline in tests (exceptions: circular imports, heavy optional deps).

### Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Unit test file | `test_<module>.py` | `test_models.py` |
| Integration test file | `test_<feature>_integration.py` | `test_service_integration.py` |
| Test class | `Test<Class>` | `TestNormalizedMember` |
| Test function | `test_<behavior>_<scenario>` | `test_add_member_success` |

### Test File Structure

```python
# tests/unit/modules/groups/test_models.py
"""Unit tests for groups module data models.

Tests cover:
- NormalizedMember creation and validation
- NormalizedGroup creation and validation
- Edge cases and error conditions
"""

import pytest
from modules.groups.models import NormalizedMember, NormalizedGroup


class TestNormalizedMember:
    """Tests for NormalizedMember model."""
    
    def test_creation_with_all_fields(self, normalized_member_factory):
        """Member can be created with all fields populated."""
        member = normalized_member_factory(
            email="test@example.com",
            id="user-123",
            role="member",
        )
        
        assert member.email == "test@example.com"
        assert member.id == "user-123"
    
    def test_creation_with_minimal_fields(self):
        """Member can be created with only required fields."""
        member = NormalizedMember(
            email="test@example.com",
            id="user-123",
            role="member",
            provider_member_id="pm-123",
        )
        
        assert member.email == "test@example.com"
    
    def test_invalid_email_raises_validation_error(self):
        """Invalid email format raises validation error."""
        with pytest.raises(ValueError, match="email"):
            NormalizedMember(
                email="not-an-email",
                id="user-123",
                role="member",
                provider_member_id="pm-123",
            )


class TestNormalizedGroup:
    """Tests for NormalizedGroup model."""
    
    def test_creation(self, normalized_group_factory):
        """Group can be created with factory."""
        group = normalized_group_factory(id="g-1", name="Test")
        
        assert group.id == "g-1"
        assert group.name == "Test"
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

### Prefer monkeypatch Over unittest.mock.patch

Use pytest's `monkeypatch` fixture for cleaner, scoped patching:

```python
# ✅ PREFERRED: monkeypatch (scoped to test)
def test_with_monkeypatch(monkeypatch):
    monkeypatch.setattr("module.dependency", mock_value)
    result = function_to_test()
    assert result == expected

# ⚠️ AVOID: unittest.mock.patch (more verbose)
from unittest.mock import patch

def test_with_patch():
    with patch("module.dependency") as mock_dep:
        mock_dep.return_value = mock_value
        result = function_to_test()
```

### Mock at System Boundaries

Patch at integration layer, not deep in libraries:

```python
# ❌ BAD: Patching deep in library internals
def test_list_groups(monkeypatch):
    monkeypatch.setattr("googleapiclient.discovery.build", mock_build)

# ✅ GOOD: Patching our integration layer
def test_list_groups(monkeypatch):
    monkeypatch.setattr(
        "integrations.google_workspace.google_directory.list_groups",
        lambda: [{"id": "g-1"}]
    )
```

### MagicMock for Complex Objects

```python
from unittest.mock import MagicMock

def test_with_configured_mock():
    """Configure mocks with explicit behavior."""
    mock_client = MagicMock()
    mock_client.list_groups.return_value = {"groups": []}
    mock_client.get_group.return_value = {"id": "g-1"}
    
    provider = GoogleWorkspaceProvider()
    provider._client = mock_client
    
    result = provider.list_groups()
    
    mock_client.list_groups.assert_called_once()
```

## Assertion Patterns

### Descriptive Assertions

Include context in assertion messages:

```python
# ✅ GOOD: Descriptive with context
assert result.is_success, f"Expected success, got: {result}"
assert len(members) == 3, f"Expected 3 members, got {len(members)}"

# ⚠️ LESS HELPFUL: Generic assertions
assert result == True
assert len(members) == 3
```

### pytest.raises for Exceptions

```python
def test_invalid_input_raises_value_error():
    """Invalid input should raise ValueError with message."""
    with pytest.raises(ValueError, match="email"):
        process_email("not-an-email")
```

### Parameterized Tests

Use `@pytest.mark.parametrize` for testing multiple cases:

```python
@pytest.mark.parametrize("email,expected_local", [
    ("user@example.com", "user"),
    ("user.name@example.com", "user.name"),
    ("user+tag@example.com", "user+tag"),
])
def test_extract_local_part(email, expected_local):
    """Test email local part extraction with multiple inputs."""
    result = extract_local_part(email)
    assert result == expected_local


@pytest.mark.parametrize("provider,expected_prefix", [
    ("google", ""),
    ("aws", "aws:"),
    ("azure", "az:"),
])
def test_get_provider_prefix(provider, expected_prefix):
    """Test provider prefix mapping."""
    assert get_provider_prefix(provider) == expected_prefix
```

## Pytest Configuration Reference

### Recommended pytest.ini

```ini
[pytest]
# Discovery
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
norecursedirs = tests/smoke .git __pycache__

# Strict mode (pytest 9.0+)
strict_markers = true
strict_config = true

# Import mode (recommended for new projects)
addopts = 
    --import-mode=importlib
    -ra
    --strict-markers
    --showlocals
    --tb=short

# Markers
markers =
    unit: Pure unit tests (<50ms, no I/O)
    integration: Integration tests (<500ms)
    slow: Tests taking >1s
    external: Tests requiring external services

# Logging
log_cli = false
log_level = WARNING

# Environment variables for tests
env =
    SLACK_TOKEN = xoxb-test-token
    # ... other test environment variables
```

### flake8-pytest-style

Consider using [flake8-pytest-style](https://github.com/m-burst/flake8-pytest-style) for linting:

```ini
# setup.cfg or .flake8
[flake8]
extend-ignore = PT009  # Use regular assert instead of pytest.approx
pytest-parametrize-names-type = tuple
pytest-fixture-no-parentheses = true
```

---

## Quick Reference

### Test Markers

| Marker | Command | Use Case |
|--------|---------|----------|
| `@pytest.mark.unit` | `pytest -m unit` | Fast, isolated unit tests |
| `@pytest.mark.integration` | `pytest -m integration` | Multi-component tests |
| `@pytest.mark.slow` | `pytest -m "not slow"` | Skip slow tests |
| `@pytest.mark.external` | `pytest -m "not external"` | Skip external service tests |

### Fixture Scopes

| Scope | Lifetime | Example Use |
|-------|----------|-------------|
| `function` | Per test | Mutable state |
| `class` | Per test class | Shared within class |
| `module` | Per test file | Expensive setup |
| `package` | Per directory | Shared across subpackages |
| `session` | Entire run | Static config |

### Common Commands

```bash
# All tests
pytest

# By marker
pytest -m unit
pytest -m "integration and not slow"

# Specific path
pytest tests/unit/modules/groups/

# With coverage
pytest --cov=modules.groups --cov-report=html

# Verbose with locals
pytest -v --showlocals

# Stop on first failure
pytest -x

# Run last failed
pytest --lf
```

---

*Last updated: January 2026 - Aligned with pytest 9.x best practices*