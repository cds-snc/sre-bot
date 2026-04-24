---
name: plugin-registration-lifespan
description: Apply pluggy registration and lifespan startup patterns for package discovery, initialization ordering, and testable startup behavior.
---

Use this skill when adding/refactoring package registration and startup behavior.

## Core Checklist

1. Register package capabilities with pluggy (no file discovery).
2. Initialize plugin/package resources during lifespan startup.
3. Keep startup wiring in platform/bootstrap layer, not business modules.
4. Ensure package contracts are typed and testable.
5. Add integration tests for startup registration and failure behavior.

## Startup Sequence Rules

- Register hookspecs before plugin registration.
- Execute discovery/registration from startup lifecycle, not module import.
- Run validation checks (`check_pending` or equivalent) to surface invalid hook implementations early.
- Keep startup behavior deterministic and observable through structured logs.

## Anti-patterns

- Side-effect registrations at import time.
- Mutable module-level registries populated during imports.
- Business modules owning bootstrap/service-wiring concerns.

## Contract Rules

- Hook signatures should be explicitly typed.
- Hook invocations should use keyword arguments for clarity and resilience.
- Feature packages should be independently registerable without central manual wiring edits.

## Test Requirements

At minimum, include:

1. Startup success path with plugin discovery and route/handler registration.
2. Startup failure path when a plugin contract is invalid.
3. Regression test ensuring registration is not import-time side effect driven.