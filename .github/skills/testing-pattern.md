# Testing Pattern

**All tests must run from `/workspace/app`**: `cd /workspace/app && pytest tests/`

## Pre-Implementation Checklist

Before writing tests:
- [ ] Tests run from `/workspace/app` directory (not `/workspace`)
- [ ] Use AAA pattern (Arrange, Act, Assert)
- [ ] Descriptive test names (`test_should_reject_when_email_invalid`)
- [ ] Factory fixtures for test data (not hardcoded instances)
- [ ] Independent tests (no shared state between tests)
- [ ] Test edge cases (empty, None, large, special characters)

---

## AAA Pattern + Descriptive Names

```python
# ✅ CORRECT
def test_should_reject_user_when_email_invalid():
    # Arrange
    user_data = {"email": "invalid"}
    
    # Act
    result = create_user(user_data)
    
    # Assert
    assert not result.is_success
    assert "email" in result.message.lower()

# ❌ FORBIDDEN
def test_user():  # Vague name
    result = create_user({"email": "bad"})  # No arrange section
    assert not result.is_success and "email" in result.message  # Multi-assert
```

---

## Factory Fixtures

```python
# ✅ CORRECT: Factory pattern
@pytest.fixture
def make_user():
    """Factory for creating test users with customizable attributes."""
    def _make(name: str = "Test User", email: str = "test@example.com"):
        return User(name=name, email=email)
    return _make

def test_user_validation(make_user):
    user = make_user(email="invalid")  # Customize as needed
    assert not user.is_valid()

# ❌ FORBIDDEN: Hardcoded fixture
@pytest.fixture
def user():
    return User(name="Test", email="test@example.com")  # Cannot customize

def test_user_validation(user):
    # Cannot test different email values without creating new fixture
    assert user.is_valid()
```

**Default-safe, override edge cases only** — factory defaults should mirror
production defaults so the happy-path test stays minimal.  Edge-case tests
override only the single field that distinguishes the scenario:

```python
# ✅ CORRECT: edge-case test only changes what matters
def test_disabled_mode(make_item, make_config):
    config = make_config(mode="disabled")  # one override
    ...

# ❌ WRONG: edge-case test duplicates all the boring defaults
def test_disabled_mode():
    config = MyModuleConfig(
        name="default",
        items={"key": MyModuleItem(token="abc", mode="disabled")},
    )
```

---

## conftest.py Placement

Place a `conftest.py` at the **package boundary** where fixtures are shared
across multiple test files.  Do **not** scatter factories as module-level
functions inside individual test files.

```
tests/unit/my_module/
├── conftest.py          ← shared factories for this entire sub-package
├── test_service.py      ← imports make_config from conftest
├── test_coordinator.py  ← same
└── test_validators.py   ← same
```

```python
# conftest.py — one canonical location for shared factories
@pytest.fixture
def make_config(make_item):
    def _make(name: str = "default", **item_kwargs):
        return MyModuleConfig(
            name=name,
            items={"key": make_item(**item_kwargs)},
        )
    return _make
```

---

## Environment Isolation (autouse)

Use an `autouse` fixture to strip package-specific environment variables
**before every test** so a local `.env` file or CI/CD pipeline cannot silently
influence unit test behaviour.  Tests that require a specific value declare it
explicitly via `monkeypatch.setenv`.

```python
# conftest.py
_MY_MODULE_ENV_KEYS = [
    "MY_MODULE_ENABLED",
    "MY_MODULE_CONFIG_SOURCE",
]

@pytest.fixture(autouse=True)
def _my_module_env_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip all MY_MODULE_* env vars before every test in this package."""
    for key in _MY_MODULE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
```

```python
# test_settings.py — no manual cleanup needed, just declare overrides
def test_enabled_flag(make_module_settings, monkeypatch):
    monkeypatch.setenv("MY_MODULE_ENABLED", "true")
    settings = make_module_settings()
    assert settings.enabled is True

# ❌ FORBIDDEN: manual delenv in every test
def test_defaults(monkeypatch):
    monkeypatch.delenv("MY_MODULE_ENABLED", raising=False)  # repeated in every test
    monkeypatch.delenv("MY_MODULE_CONFIG_SOURCE", raising=False)
    settings = MyModuleSettings()
    assert settings.enabled is False
```

---

## Pydantic-Settings: Bypass .env on Disk

`pydantic-settings` reads `.env` from disk even when all process env vars are
cleared.  Always pass `_env_file=None` when constructing settings in unit tests,
or wrap it in a factory fixture so the bypass is automatic:

```python
# ✅ CORRECT: wrap in a factory fixture
@pytest.fixture
def make_module_settings():
    def _make(**overrides):
        return MyModuleSettings(_env_file=None, **overrides)
    return _make

def test_defaults(make_module_settings):
    settings = make_module_settings()
    assert settings.enabled is False

# ❌ FORBIDDEN: direct instantiation in tests — reads .env file from disk
def test_defaults():
    settings = MyModuleSettings()  # picks up developer .env on local machine
    assert settings.enabled is False  # may pass locally, fail in CI
```

---

## Cleanup with Fixtures

```python
# ✅ CORRECT: Automatic cleanup
@pytest.fixture
def temp_file():
    """Create temp file, clean up after test."""
    path = "/tmp/test.txt"
    with open(path, "w") as f:
        f.write("test")
    yield path
    if os.path.exists(path):
        os.remove(path)

def test_file_processing(temp_file):
    result = process_file(temp_file)
    assert result.is_success
    # temp_file automatically deleted

# ❌ FORBIDDEN: Manual cleanup
def test_file_processing():
    path = "/tmp/test.txt"
    with open(path, "w") as f:
        f.write("test")
    result = process_file(path)
    os.remove(path)  # Might not run if assertion fails
    assert result.is_success
```

---

## Monkeypatch

```python
# ✅ CORRECT: Use monkeypatch fixture
def test_with_env_vars(monkeypatch):
    monkeypatch.setenv("AWS__AWS_REGION", "us-west-2")
    monkeypatch.setattr("module.function", lambda: "mocked")
    
    settings = get_settings()
    assert settings.aws.aws_region == "us-west-2"

# ❌ FORBIDDEN: Manual patching
import os
def test_with_env_vars():
    os.environ["AWS__AWS_REGION"] = "us-west-2"  # Pollutes environment
    settings = get_settings()
    del os.environ["AWS__AWS_REGION"]  # Manual cleanup
```

---

## Mock Assertions

Call `assert_*` methods directly on the mock — never prepend `assert` to a mock attribute access.

```python
# ✅ CORRECT: real assertion methods — raise AssertionError on failure
mock_fn.assert_called_once_with("arg", key="val")  # called exactly once with these args
mock_fn.assert_called_once()                        # called exactly once, any args (3.6+)
mock_fn.assert_called_with("arg")                   # most recent call matches
mock_fn.assert_not_called()
assert mock_fn.call_count == 2                      # exact count check

# ❌ FORBIDDEN: silently passes — never raises AssertionError
assert mock_fn.called_once_with("arg")  # `called_once_with` is NOT a real method;
                                         # MagicMock auto-creates it as a truthy child Mock
assert mock_fn.called                   # only checks called≥1; ignores call count and args
```

**Root cause**: `MagicMock` creates any attribute on demand. `called_once_with` is not a real
method, so accessing it returns a new truthy `Mock` — the `assert` always passes even if the
mock was never called. Use the `assert_` prefixed methods which are real and raise on failure.

---

## FastAPI Testing

```python
# ✅ CORRECT: Override dependencies, cleanup
from fastapi.testclient import TestClient

def test_api_endpoint(app, mock_settings):
    app.dependency_overrides[get_settings] = lambda: mock_settings
    
    try:
        client = TestClient(app)
        response = client.get("/api/v1/config")
        
        assert response.status_code == 200
        assert response.json()["region"] == "us-west-2"
    finally:
        app.dependency_overrides.clear()

# ❌ FORBIDDEN: No cleanup, hardcoded values
def test_api_endpoint():
    client = TestClient(app)  # Uses real settings
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    # Dependency override never cleared
```

---

## Parametrize

```python
# ✅ CORRECT: Test multiple cases efficiently
@pytest.mark.parametrize("invalid_email", [
    "",
    "no-at-sign",
    "@example.com",
    "spaces in@example.com",
])
def test_should_reject_invalid_emails(invalid_email):
    result = validate_email(invalid_email)
    assert not result.is_success

# Multiple parameters
@pytest.mark.parametrize("name,expected", [
    ("user@example.com", True),
    ("invalid", False),
    ("", False),
])
def test_email_validation(name, expected):
    result = validate_email(name)
    assert result.is_success == expected

# ❌ FORBIDDEN: Repetitive tests
def test_rejects_empty_email():
    assert not validate_email("").is_success

def test_rejects_no_at_sign():
    assert not validate_email("invalid").is_success
    
# ... many similar tests
```

---

## OperationResult Testing

```python
# ✅ CORRECT: Test result properties (not methods)
def test_service_returns_success():
    result = service.create_user({"name": "Test"})
    
    assert result.is_success  # Property, not is_success()
    assert result.data["id"] is not None
    assert result.error_code is None

def test_service_returns_error():
    result = service.create_user({"name": ""})
    
    assert not result.is_success
    assert result.error_code == "VALIDATION_ERROR"
    assert "name" in result.message.lower()

# ❌ FORBIDDEN: Calling is_success as method
def test_service():
    result = service.create_user({"name": "Test"})
    assert result.is_success()  # WRONG - it's a property
```

---

## Test Markers

```python
# ✅ CORRECT: Use markers to categorize tests
@pytest.mark.unit
def test_user_validation():
    """Fast, isolated unit test."""
    assert validate_user({"name": ""}).is_success is False

@pytest.mark.integration
def test_user_api_endpoint(app):
    """Test with FastAPI app."""
    client = TestClient(app)
    response = client.post("/api/v1/users", json={"name": "Test"})
    assert response.status_code == 200

@pytest.mark.slow
def test_bulk_user_import():
    """Slow test (large dataset)."""
    users = [{"name": f"User{i}"} for i in range(10000)]
    result = import_users(users)
    assert result.is_success

@pytest.mark.skip(reason="Feature not implemented yet")
def test_future_feature():
    assert False

# Run specific markers: pytest -m unit
# Skip markers: pytest -m "not slow"
```

---

## Edge Cases (Required)

```python
# ✅ CORRECT: Test edge cases
def test_empty_input():
    result = process_data("")
    assert not result.is_success

def test_none_input():
    result = process_data(None)
    assert not result.is_success

def test_large_input():
    large_data = "x" * 1_000_000
    result = process_data(large_data)
    assert result.is_success

def test_special_characters():
    result = process_data("test@#$%^&*()")
    assert result.is_success

def test_unicode():
    result = process_data("test 你好 👍")
    assert result.is_success

# ❌ FORBIDDEN: Only happy path
def test_process_data():
    result = process_data("normal input")
    assert result.is_success
    # Missing: empty, None, large, special chars
```

---

## Anti-Patterns

### Don't Test Private Methods

```python
# ❌ FORBIDDEN: Testing private methods
def test_private_validation():
    user = User(name="Test")
    assert user._validate_name() is True  # Testing private method

# ✅ CORRECT: Test public interface
def test_user_creation_validates_name():
    user = User(name="")
    assert not user.is_valid()  # Public method
```

### One Behavior Per Test

```python
# ❌ FORBIDDEN: Multiple behaviors
def test_user():
    assert user.save()
    assert user.name == "Test"
    assert user.email == "test@example.com"
    assert user.is_active

# ✅ CORRECT: Separate tests
def test_user_saves_successfully():
    assert user.save()

def test_user_has_correct_name():
    assert user.name == "Test"

def test_user_is_active_by_default():
    assert user.is_active
```

### Independent Tests

```python
# ❌ FORBIDDEN: Shared state
user = None

def test_create_user():
    global user
    user = User(name="Test")
    assert user is not None

def test_save_user():
    # Depends on test_create_user running first
    assert user.save()

# ✅ CORRECT: Independent with fixtures
@pytest.fixture
def user():
    return User(name="Test")

def test_create_user(user):
    assert user is not None

def test_save_user(user):
    assert user.save()
```

---

## Common Violations

### Running from Wrong Directory

```bash
# ❌ FORBIDDEN
cd /workspace
pytest app/tests/  # Settings import fails

# ✅ CORRECT
cd /workspace/app
pytest tests/
```

### Missing Edge Cases

```python
# ❌ FORBIDDEN: Only happy path
def test_validate_email():
    assert validate_email("test@example.com").is_success

# ✅ CORRECT: Test edge cases
@pytest.mark.parametrize("invalid", ["", None, "@", "test", "test@"])
def test_validate_email_rejects_invalid(invalid):
    assert not validate_email(invalid).is_success

def test_validate_email_accepts_valid():
    assert validate_email("test@example.com").is_success
```

### Hardcoded Test Data

```python
# ❌ FORBIDDEN
def test_user_creation():
    user = User(name="Test", email="test@example.com")
    assert user.is_valid()

def test_user_with_different_email():
    user = User(name="Test", email="other@example.com")  # Duplicated
    assert user.is_valid()

# ✅ CORRECT: Factory fixture
@pytest.fixture
def make_user():
    def _make(**kwargs):
        defaults = {"name": "Test", "email": "test@example.com"}
        return User(**{**defaults, **kwargs})
    return _make

def test_user_creation(make_user):
    user = make_user()
    assert user.is_valid()

def test_user_with_different_email(make_user):
    user = make_user(email="other@example.com")
    assert user.is_valid()
```

---

## Final Checklist

Before committing tests:
- [ ] All tests pass: `cd /workspace/app && pytest tests/ -v`
- [ ] Run from `/workspace/app` directory
- [ ] Descriptive test names (test_should_action_when_condition)
- [ ] AAA pattern (Arrange, Act, Assert)
- [ ] Factory fixtures for test data (default-safe, override edge cases only)
- [ ] Shared factories in `conftest.py` at the package boundary, not duplicated per file
- [ ] `autouse` env isolation fixture strips package env vars before every test
- [ ] pydantic-settings constructed with `_env_file=None` (via factory fixture)
- [ ] Edge cases tested (empty, None, large, special chars)
- [ ] Independent tests (no shared state)
- [ ] Cleanup handled by fixtures
- [ ] No secrets in test code
- [ ] Coverage >80%: `pytest --cov=modules --cov-report=term-missing`
- [ ] Fix linting issues: `flake8 .`
- [ ] Check formatting issues: `black . --check`
- [ ] Check for type errors: `mypy .`
