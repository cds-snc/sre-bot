---
name: Tests Python Rules
description: Use for tests under app/tests; enforces location, naming, and focused assertions.
applyTo: app/tests/**/*.py
---

- Tests in `app/tests/` with `unit/` and `integration/`. Names: `test_<feature>_<entity>_<what>.py` (ADR-0062).
- Cover success, failure mapping, and dependency variation paths.
- `app.dependency_overrides` for service substitution; always `finally` clear (ADR-0062).
- Test doubles must conform to Protocol contracts (ADR-0077). Narrow-slice fixtures only (ADR-0056).
- Clear `@lru_cache` between tests. Deterministic — no network calls (ADR-0054).
- No `app/tests/smoke/*` unless explicitly requested with env vars configured.
