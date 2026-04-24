---
name: testing-standards
description: Apply project testing standards for app/tests layout, naming, dependency overrides, and route/service coverage.
---

# Testing Standards

Use this skill when creating or updating tests.

## Placement and Naming

1. Place tests under `app/tests/` only.
2. Use feature-prefix naming (for example, `test_groups_routes.py`).
3. Avoid ambiguous names like `test_routes.py`.

## Structure Guidance

- Unit tests: `app/tests/unit/...`
- Integration tests: `app/tests/integration/...`
- Fixtures and factories should remain under shared test support locations.

## Route Testing

For FastAPI endpoints, cover:

1. Success path with response schema assertions.
2. Failure mapping path (status and stable error detail).
3. Dependency variation path (auth/permission/override where relevant).

Use dependency overrides instead of patching unrelated internals when possible.

## Service Testing

- Test business rules with direct service calls.
- Use protocol/fake implementations for external dependencies.
- Keep tests deterministic and avoid network dependence.

## Anti-patterns

- Tests outside `app/tests`.
- Heavy integration setup for pure unit behavior.
- Asserting only status code without payload/behavior assertions.
