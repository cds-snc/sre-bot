---
name: plugin-registration-lifespan
description: Apply pluggy registration and lifespan startup patterns for package discovery, initialization ordering, and testable startup behavior.
---

Use when adding/refactoring package registration or startup behavior.

## Startup Phases (ADR-0046)

1. Configuration → 2. Infrastructure → 3. Discovery/Registration → 4. Feature Activation → 5. Transport → 6. Background

Failure in any phase terminates startup (fail-fast). Shutdown is reverse order.

## Plugin Registration Checklist (ADR-0049)

1. `auto_discover_plugins` scans `app/packages/*` during phase 3.
2. Hookspecs registered before plugins.
3. `pm.check_pending()` after registration.
4. Singleton plugin manager via `@lru_cache(maxsize=1)`.
5. Keyword-only hook invocation.
6. `startup_warmup` failures propagate — no silent continue.
7. Zero-touch extension: new packages need no lifespan changes.
8. `__init__.py`: only `@hookimpl` functions. No side effects.

## Background Jobs (ADR-0058)

- Register via `register_background_job` hookspec.
- Tier 1 (idempotent) vs Tier 2 (DynamoDB lock). `safe_run()` error isolation.
- Production-only (`PREFIX == ""`). Registration in all envs; execution in prod only.

## Anti-patterns

- Import-time registrations or mutable module-level registries.
- Business modules owning bootstrap wiring.
- Silent warmup failures. Dynamic registration during request handling.

## Tests (ADR-0062)

1. Startup success: plugin discovery + registration verified.
2. Startup failure: invalid contract triggers fail-fast.
3. No import-time side effects (regression).
4. Idempotent handler registration across repeated startup.
5. Warmup failure policy exercised.