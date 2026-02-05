# SRE Bot Copilot Instructions

**Root**: `/workspace/app` | **Run**: `cd /workspace/app`  
**Skills**: `.github/skills/` directory contains detailed pattern enforcement rules  
**ADRs**: `docs/decisions/tier-1-foundation/` contains architectural decisions

---

## ENFORCEMENT MODE

**Before generating ANY code**:
1. Read applicable skill documents from `.github/skills/`
2. Verify code follows all patterns in skills
3. Run pre-implementation checklists
4. If any rule violated, REJECT code generation and explain violation

**Critical Skills** (check EVERY time):
- `imports-pattern.md` - Import rules (frequently violated)
- `settings-singleton.md` - Settings access
- `logging-pattern.md` - Structured logging
- `no-async-pattern.md` - Synchronous code only
- `type-hints-pattern.md` - Type annotations
- `testing-pattern.md` - Test patterns when writing tests

---

## Quick Reference

| Rule | ✅ Correct | ❌ Forbidden |
|------|-----------|-------------|
| **Imports** | Top-level only | Inside functions |
| **Settings** | `from infrastructure.services import SettingsDep, get_settings` | `Settings()` direct instantiation |
| **Async** | `def func():` | `async def / await` (except lifespan) |
| **Logging** | `log = logger.bind(user_id=...)` | Manual `code_namespace` binding |
| **Types** | `def func(x: str) -> int:` | Missing type hints |
| **Services** | `__init__(self, settings: Settings):` | `__init__(self): self.settings = get_settings()` |
| **Results** | `if result.is_success:` | `if result.is_success():` |

**Full details**: See skills documents in `.github/skills/`

---

## Validation

```bash
cd /workspace/app
mypy . && flake8 . && black --check . && pytest tests/ -v
black .  # Fix formatting
```

Run after 3-5 changes, before PR/complete.

---

## Module Structure

```
modules/feature/
├── schemas.py controllers.py service.py
├── validation.py responses.py
├── providers/ tests/
```

---

## Skills Documentation

Detailed patterns with code examples and checklists:

1. **[imports-pattern.md](.github/skills/imports-pattern.md)** ⚠️ TOP PRIORITY
2. **[settings-singleton.md](.github/skills/settings-singleton.md)**
3. **[logging-pattern.md](.github/skills/logging-pattern.md)**
4. **[provider-pattern.md](.github/skills/provider-pattern.md)**
5. **[initialization-pattern.md](.github/skills/initialization-pattern.md)**
6. **[no-async-pattern.md](.github/skills/no-async-pattern.md)**
7. **[type-hints-pattern.md](.github/skills/type-hints-pattern.md)**
8. **[testing-pattern.md](.github/skills/testing-pattern.md)**

**Read skills before implementing patterns.**

---

## Workflow Guides

Process and planning documentation (optional reference):

- **[Implementation Planning](workflows/implementation-planning.md)** - Feature development workflow