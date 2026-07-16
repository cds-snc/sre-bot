---
name: plugin-registration-lifespan
description: Apply pluggy registration and lifespan startup patterns for package discovery, initialization ordering, and testable startup behavior.
---

# Plugin Registration and Lifespan Startup

Use this skill when adding/refactoring package registration and startup behavior.

## Core Checklist

1. Register package capabilities with pluggy via entry-points declared in `pyproject.toml` (`[project.entry-points."<marker_namespace>"]`), loaded once at startup with `pm.load_setuptools_entrypoints(...)` — never via import-time registration, and not via filesystem discovery (the `auto_discover_plugins` walk is being removed per `decisions/plugins.md`). Adding a feature means adding its one entry-point line; discovery is declarative and reviewed, not implicit from disk.
2. Initialize plugin/package resources during lifespan startup.
3. Keep startup wiring in platform/bootstrap layer, not business modules.
4. Ensure package contracts are typed and testable.
5. Add integration tests for startup registration and failure behavior.

## Startup Sequence Rules

- Register hookspecs before plugin registration.
- Apply `pm.set_blocked(<feature>)` for feature-flag-disabled features before `load_setuptools_entrypoints`, not with conditionals inside a hookimpl.
- Execute discovery/registration from startup lifecycle, not module import.
- Run validation checks (`check_pending` or equivalent) to surface invalid hook implementations early.
- Fail fast: an unimportable entry-point target or a raising hookimpl terminates boot. Do not catch-and-continue registration errors.
- Keep startup behavior deterministic and observable through structured logs.

## Event Handler Registration Pattern

- Register event handlers inside a startup hook (`startup_warmup` or dedicated registration hook), never via import-time decorators in module body.
- Make registration idempotent by checking existing handlers before registering, to avoid duplicate handlers in tests and repeated startup paths.
- Keep handler functions import-safe; only registration should happen at startup.

## Warmup Failure Policy Pattern

- Choose and document one startup behavior per package: fail-startup (raise) or degrade (log and gate routes).
- If using degrade mode, expose a deterministic readiness gate so requests return 503 until warmup dependencies are healthy.
- Do not silently swallow warmup failures; include actionable structured log fields (config source, hint, error type).

## Anti-patterns

- Side-effect registrations at import time.
- Mutable module-level registries populated during imports.
- Business modules owning bootstrap/service-wiring concerns.
- Catch-and-continue warmup blocks that only log errors but still allow broken request paths.

## Contract Rules

- Hook signatures should be explicitly typed.
- Hook invocations should use keyword arguments for clarity and resilience.
- Feature packages register declaratively through a single `pyproject.toml` entry-point line, not through composition-root code edits; the host performs no per-feature manual `pm.register()` wiring.

## Test Requirements

At minimum, include:

1. Startup success path with plugin discovery and route/handler registration.
2. Startup failure path when a plugin contract is invalid.
3. Regression test ensuring registration is not import-time side effect driven.
4. Regression test proving event-handler registration is idempotent across repeated startup/test setup.
5. Startup warmup failure test for the selected policy (fail-startup or degrade-with-503 gate).