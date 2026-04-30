---
name: testing-standards
description: Apply project testing standards for app/tests layout, naming, dependency overrides, and route/service coverage.
---

Use when creating or updating tests.

## Layout (ADR-0062)

- All tests in `app/tests/` with `unit/` and `integration/`.
- Names: `test_<feature>_<entity>_<what>.py`. No generic names.

## Route Tests

1. Success path: response schema + status code.
2. Failure mapping: OperationResult error → HTTP status + RFC 9457 body.
3. Dependency variation: auth/permission branches.

Use `app.dependency_overrides`; always `finally` clear.

## Service Tests

- Direct service calls with Protocol-conformant fakes for Category A dependencies (ADR-0077).
- Assert on `OperationResult` status, not provider-specific details (ADR-0050).
- Deterministic — no network calls.

## Fixtures

- Narrow-slice settings only (ADR-0056).
- Clear `@lru_cache` between tests via autouse fixtures.

## Anti-patterns

- Tests outside `app/tests/`. Heavy integration for unit behavior.
- Status-code-only assertions. Missing `dependency_overrides` cleanup.
- Non-conformant test doubles. Full Settings objects in fixtures.
