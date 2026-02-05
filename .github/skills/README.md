# Agent Skills Documentation

This directory contains detailed pattern enforcement rules for coding agents working on the SRE Bot codebase.

## Purpose

These skills documents ensure all code adheres to architectural decisions documented in `docs/decisions/tier-1-foundation/`. Each skill provides:

1. **Pattern enforcement rules** - Clear correct/forbidden patterns
2. **Code examples** - Concrete implementations
3. **Pre-implementation checklists** - Validation before code generation
4. **Reasoning** - Why patterns exist

## Skills Index

### Critical (Check Every Time)

1. **[imports-pattern.md](./imports-pattern.md)** ⚠️ MOST VIOLATED
   - All imports at module top (never inside functions)
   - Settings via `SettingsDep` or `get_settings()`
   - Services via provider functions
   - Import order enforcement

2. **[settings-singleton.md](./settings-singleton.md)**
   - `@lru_cache` singleton pattern
   - Pydantic Settings validation
   - Dependency injection
   - Environment variable naming

3. **[logging-pattern.md](./logging-pattern.md)**
   - Structlog with OpenTelemetry
   - Request-scoped context binding
   - Forbidden automatic fields
   - No print() statements

4. **[no-async-pattern.md](./no-async-pattern.md)**
   - Synchronous code only (except lifespan)
   - Thread-based concurrency
   - No asyncio

5. **[type-hints-pattern.md](./type-hints-pattern.md)**
   - Required for all functions
   - Parameter and return types
   - OperationResult patterns
   - Optional handling

6. **[testing-pattern.md](./testing-pattern.md)**
   - AAA pattern (Arrange, Act, Assert)
   - Factory fixtures for test data
   - Independent tests, edge cases
   - FastAPI testing, parametrize

### Architectural Patterns

7. **[provider-pattern.md](./provider-pattern.md)**
   - Service provider functions
   - Dependency injection
   - Lazy imports for conditional providers
   - Module-level registries

8. **[initialization-pattern.md](./initialization-pattern.md)**
   - FastAPI lifespan context manager
   - Sequential initialization phases
   - Socket Mode threading
   - Graceful shutdown

## Usage for Coding Agents

### Before Generating Code

1. **Identify applicable skills** - Which patterns does this code touch?
2. **Read skill documents** - Review patterns and forbidden examples
3. **Run pre-implementation checklist** - Verify all requirements met
4. **Generate code** - Follow patterns exactly
5. **Validate** - Ensure no forbidden patterns present

### If Rule Violated

**DO NOT generate code**. Instead:
1. Explain which skill rule is violated
2. Show the forbidden pattern
3. Provide correct pattern from skill document
4. Ask user to confirm approach

## Common Violations

### 1. Imports Inside Functions (⚠️ Most Frequent)

```python
# ❌ WRONG
def my_function():
    from infrastructure.services import get_settings  # VIOLATION
    settings = get_settings()

# ✅ CORRECT
from infrastructure.services import get_settings

def my_function():
    settings = get_settings()
```

**Skill**: `imports-pattern.md` Section 1

### 2. Direct Settings Instantiation

```python
# ❌ WRONG
from infrastructure.configuration import Settings
settings = Settings()  # VIOLATION

# ✅ CORRECT
from infrastructure.services import get_settings
settings = get_settings()
```

**Skill**: `settings-singleton.md`

### 3. Manual Code Namespace Binding

```python
# ❌ WRONG
log = logger.bind(code_namespace="modules.groups")  # VIOLATION

# ✅ CORRECT
log = logger.bind(user_id=user_id, request_id=request_id)
```

**Skill**: `logging-pattern.md` Section "Automatic Fields"

### 4. Async Functions

```python
# ❌ WRONG
async def process_data():  # VIOLATION (not lifespan)
    result = await operation()

# ✅ CORRECT
def process_data():
    result = operation()
```

**Skill**: `no-async-pattern.md`

### 5. Missing Type Hints

```python
# ❌ WRONG
def process(data):  # VIOLATION - no types
    return data

# ✅ CORRECT
def process(data: Dict[str, Any]) -> Dict[str, Any]:
    return data
```

**Skill**: `type-hints-pattern.md`

## Relationship to ADRs

Skills implement patterns from architectural decision records:

| Skill | Source ADR |
|-------|------------|
| imports-pattern.md | Copilot instructions |
| settings-singleton.md | `application-lifecycle/02-settings-singleton.md` |
| logging-pattern.md | Copilot instructions, logging standards |
| provider-pattern.md | `application-lifecycle/04-provider-discovery.md` |
| initialization-pattern.md | `application-lifecycle/01-fastapi-lifespan-pattern.md` |
| no-async-pattern.md | Copilot instructions |
| type-hints-pattern.md | Copilot instructions |

## Validation

After generating code:

```bash
cd /workspace/app

# Type checking
mypy .

# Linting
flake8 .

# Formatting
black --check .

# Tests
pytest tests/ -v
```

All checks must pass before code complete.

## Updates

When architectural decisions change:
1. Update ADR in `docs/decisions/`
2. Update corresponding skill document
3. Update `copilot-instructions.md` if needed
4. Add example to skill if pattern clarifies common violation
