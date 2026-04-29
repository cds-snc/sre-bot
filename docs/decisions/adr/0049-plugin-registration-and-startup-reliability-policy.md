---
adr_id: ADR-0049
title: "Plugin Registration and Startup Reliability Policy"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Package and Plugin Architecture
secondary_domains:
  - Runtime and Lifecycle
  - Dependency and Composition
owners:
  - SRE Team
date_created: 2026-04-28
last_updated: 2026-04-28
last_reviewed: 2026-04-28
next_review_due: 2026-08-26
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0046
  - ADR-0048
impacts:
  - ADR-0056
  - ADR-0057
  - ADR-0058
supersedes:
  - ADR-0013
  - ADR-0017
  - ADR-0026
  - ADR-0027
superseded_by: []
review_state: current
related_records:
  - ADR-0044
  - ADR-0045
  - ADR-0046
  - ADR-0048
related_packages:
  - app/packages/access
---

# Plugin Registration and Startup Reliability Policy

## Context

- Problem statement: Plugin registration mechanics were fragmented across four legacy ADRs: ADR-0013 (Plugin Managers) defined the pluggy PluginManager singleton pattern, ADR-0017 (Feature Package Startup Failure Policy) defined fail-fast vs. degrade startup behavior, ADR-0026 (Explicit Registration Pattern) rejected import-time side effects in favor of startup-driven discovery, and ADR-0027 (Pluggy Plugin System Integration) provided comprehensive pluggy usage guidance. These four records collectively govern plugin lifecycle but with overlapping scope and inconsistent depth.
- Business/operational drivers:
  - Consolidate all plugin registration and startup reliability rules into one Tier-2 standard.
  - Tie startup failure behavior directly to the plugin registration contract.
  - Ensure that adding a new package under `app/packages/` requires no changes to lifespan code.
  - Prevent silent startup degradation that allows broken request paths to serve traffic.
- Constraints:
  - Pluggy is the plugin framework (constrained by ADR-0048 Boundary 4 — no import-time side effects).
  - All registration occurs during lifespan startup (constrained by ADR-0046 Invariant 2 — phase 3 Discovery and Registration).
  - Registries are immutable after startup (constrained by ADR-0046 Invariant 5).
  - Failed startup must terminate the process (constrained by ADR-0046 Invariant 3 — fail-fast).
- Non-goals:
  - This record does not define specific hook specifications or hook call ordering conventions (those are implementation details within each plugin manager).
  - This record does not define provider composition patterns (delegated to ADR-0056).

## Decision

- Chosen approach: Establish a unified Tier-2 standard that governs the complete plugin lifecycle from discovery through startup validation, including failure behavior.
- Why this approach: The four source ADRs are tightly coupled — registration mechanics, discovery strategy, validation checks, and failure policy are inseparable aspects of one lifecycle. Consolidation eliminates redundancy and creates a single enforceable reference.

### Standard 1: Startup-Driven Filesystem Discovery

Plugin discovery must occur during lifespan startup via explicit filesystem scanning of designated package directories (`app/packages/`, and transitionally `app/modules/`). Discovery must use `auto_discover_plugins` or equivalent startup-time scanning. No plugin may be discovered or registered at import time.

### Standard 2: Hookspec-Before-Registration Ordering

Hook specifications must be registered with the PluginManager before any plugin is registered. This enables immediate validation: if a plugin implements a hook that has no matching specification, the error is detectable at registration time rather than at call time.

### Standard 3: Post-Registration Validation

After all plugins are registered, `pm.check_pending()` must be called to validate that all hook implementations have matching specifications. Any unmatched hook implementation (without `optionalhook=True`) must raise `PluginValidationError` and terminate startup.

### Standard 4: Singleton Plugin Manager

Each plugin manager instance must be created once per process via `@lru_cache(maxsize=1)` and reused for the process lifetime. Creating multiple plugin manager instances for the same hook domain is prohibited.

### Standard 5: Keyword-Only Hook Invocation

All pluggy hook calls must use keyword arguments exclusively. Positional arguments to hook calls raise `HookCallError` at runtime; this standard makes the constraint explicit and reviewable.

### Standard 6: Fail-Fast Startup Warmup

Every feature package that exposes a `startup_warmup` hookimpl must follow these rules:

| Feature state | `startup_warmup` behavior |
|---------------|---------------------------|
| Enabled + warmup succeeds | Normal startup; no exception. |
| Enabled + warmup fails (permanent: config error, missing file, invalid JSON) | Exception propagates to lifespan; process terminates with non-zero exit. |
| Enabled + warmup fails (transient: network blip, DNS timeout, provider health check) | Bounded retry with backoff (≤ 3 attempts). If all retries fail, exception propagates to lifespan; process terminates. |
| Disabled (`settings.enabled = False`) | Log structured warning, return immediately; no exception. |

**Silent-continue** (catching exceptions without re-raising when the feature is enabled) is explicitly prohibited. This includes broad `try/except Exception` blocks that log and swallow the error.

**Transient retry guidance:** Retry logic for transient startup errors belongs within the warmup implementation (or in the called service/loader), not at the pluggy call site. Retries must be bounded (≤ 3 attempts) with exponential backoff. If all retries are exhausted, the exception must propagate. Unbounded retry loops during startup are prohibited.

If a specific exception needs a better log message before propagation, use `except SpecificError as exc: logger.error(...); raise`.

### Standard 7: Zero-Touch Package Extension

Adding a new package under `app/packages/` must not require changes to the lifespan function, plugin manager initialization, or any file outside the new package directory. The startup-driven discovery mechanism must detect and register the new package automatically.

**Discoverable package contract:** A package is discoverable when it meets all of the following conditions:
1. It is a Python package directory under `app/packages/` (contains `__init__.py`).
2. Its `__init__.py` contains at least one function decorated with `@hookimpl`.
3. The package is importable (no syntax errors, no unresolved top-level imports).

`auto_discover_plugins` scans top-level directories under the configured base paths and attempts to import each as a module. Packages that fail to import are logged as errors and treated as startup failures per Standard 6.

### Standard 8: No Import-Time Side Effects in Package Init

Package `__init__.py` files must only define `@hookimpl`-decorated functions and module-level constants. They must not execute registration calls, mutate global dictionaries, instantiate services, or perform I/O. The `@hookimpl` decorator is permitted because it is a metadata marker that does not execute side effects.

## Alternatives Considered

1. Maintain four separate plugin-related ADRs:
   - Pros: Smaller individual records.
   - Cons: Four records for one lifecycle creates navigation overhead and contradiction risk.
   - Why not chosen: Plugin registration, discovery, validation, and failure behavior are inseparable.
2. Allow degrade-mode startup as the default:
   - Pros: Non-feature routes remain available during partial misconfiguration.
   - Cons: In ECS, broken features cannot be fixed without a new task definition; the process looks healthy but serves 503s indefinitely with no automatic recovery.
   - Why not chosen: Fail-fast is the safer default for the current deployment model; degrade mode is documented as a future option with strict requirements.
3. Use decorator-based auto-registration instead of pluggy:
   - Pros: Simpler mental model; no pluggy dependency.
   - Cons: Import-time side effects; per-subsystem boilerplate for discovery, registration, activation, and reset; test pollution from module-level mutable registries.
   - Why not chosen: Explicitly rejected; documented in source ADR-0026.

## Consequences

- Positive impacts:
  - Single authoritative record for the complete plugin lifecycle eliminates contradictions across four source ADRs.
  - Fail-fast startup prevents silent degradation; ECS health checks detect failures immediately.
  - Zero-touch extension reduces friction for new package development.
  - Post-registration validation catches configuration errors before traffic is served.
- Tradeoffs accepted:
  - Fail-fast means a single bad configuration value prevents the entire application from starting.
  - Pluggy is a runtime dependency; replacing it would require amending this standard.
  - All eight standards must be followed together; partial adoption is non-compliant.
- Risks introduced:
  - A misconfigured environment variable in one feature package takes down all unrelated routes.
  - Pluggy's hook ordering and wrapper semantics have a learning curve.
- Mitigations:
  - Pydantic settings validation provides clear error messages at startup, identifying exactly which configuration value failed.
  - Staging environment testing with `entry.sh` variables catches configuration errors before production deployment.
  - Degrade mode is documented as a future escape hatch for genuinely optional features, with strict implementation requirements.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Standards 1, 7, and 8 directly govern how `app/packages/` integrates with the application lifecycle without coupling to infrastructure or lifespan code.
- Type boundary impact: Not directly applicable; deferred to ADR-0065.
- Startup/plugin registration impact: This is the authoritative startup/plugin registration standard. Constrained by ADR-0046 lifecycle invariants 2, 3, and 5.
- Settings partitioning impact: Standard 6 requires each feature package to validate its settings during `startup_warmup`, complementing ADR-0047 Principle 3.

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
  - Pluggy documentation: hook specifications, registration, check_pending(), exception handling (https://pluggy.readthedocs.io/en/stable/).
  - ASGI Lifespan Protocol v2.0: startup.failed event semantics.
  - FastAPI lifespan events documentation.
  - Twelve-Factor App: Factor IX (Disposability — fast startup).
  - pytest plugin ecosystem: real-world pluggy usage patterns.
- Alignment summary:
  - Startup-driven discovery aligns with pluggy's intended usage (register, then call hooks).
  - Fail-fast startup aligns with ASGI startup.failed protocol and Factor IX.
  - Keyword-only hook invocation is enforced by pluggy itself; this standard makes it explicit.
  - check_pending() validation is a pluggy best practice for catching implementation errors early.
- Intentional deviations: None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Consolidates ADR-0013, ADR-0017, ADR-0026, and ADR-0027 into one plugin lifecycle standard with fail-fast startup policy.
- Follow-up actions:
  - Mark ADR-0013, ADR-0017, ADR-0026, and ADR-0027 as superseded with `superseded_by: [ADR-0049]`.
  - Remove `try/except Exception` blocks from existing package `startup_warmup` hookimpls.
  - Ensure downstream standards (ADR-0056, ADR-0057, ADR-0058) reference this record in `constrained_by`.

## Source References

1. Source title: Pluggy Documentation — Plugin Registration and Hook Specifications
   - URL: https://pluggy.readthedocs.io/en/stable/
   - Publisher/maintainer: pytest-dev / pluggy
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Authoritative source for registration ordering, check_pending(), exception handling, and keyword-only hook calls.
2. Source title: ASGI Lifespan Protocol v2.0
   - URL: https://asgi.readthedocs.io/en/latest/specs/lifespan.html
   - Publisher/maintainer: ASGI community
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Defines startup.failed event semantics that underpin fail-fast behavior.
3. Source title: FastAPI Lifespan Events
   - URL: https://fastapi.tiangolo.com/advanced/events/
   - Publisher/maintainer: Sebastián Ramírez / FastAPI
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Lifespan context manager is the sole entry point for startup/shutdown logic.
4. Source title: plugin-registration-lifespan SKILL.md
   - URL: .github/skills/plugin-registration-lifespan/SKILL.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Warmup failure policy pattern and startup-driven discovery conventions.
5. Source title: ADR-0013, ADR-0017, ADR-0026, ADR-0027 (Legacy)
   - URL: docs/decisions/adr/superseded/
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Source records being consolidated; plugin lifecycle standards extracted.

## Implementation Guidance

- Required changes:
  - Mark ADR-0013, ADR-0017, ADR-0026, ADR-0027 as `status: Superseded` and add `superseded_by: [ADR-0049]`.
  - Remove `try/except Exception` blocks from `startup_warmup` hookimpls in all packages where `settings.enabled = True`.
  - Validate that `pm.check_pending()` is called after all plugin registrations during lifespan startup.
  - Ensure `auto_discover_plugins` is the discovery mechanism in production lifespan code.
- Validation and quality gates:
  - Test: warmup failure raises and prevents startup when feature is enabled.
  - Test: warmup returns None without raising when feature is disabled.
  - Test: adding a new package under `app/packages/` with `@hookimpl` is discovered without lifespan changes.
  - ADR-0051 taxonomy check: confirm this is a Tier-2 Standard, not Tier-1 Principle.
- Test strategy and acceptance criteria impact:
  - Existing warmup tests must be updated to assert exception propagation instead of silent continuation.
  - New packages must include warmup success and warmup failure test cases.

## Change Log

- 2026-04-28: Revised Standard 6 to add bounded retry guidance for transient startup errors. Revised Standard 7 to define discoverable package contract. Resolves blockers identified in challenge review.
- 2026-04-28: Created canonical Tier-2 plugin registration and startup reliability standard; supersedes ADR-0013, ADR-0017, ADR-0026, ADR-0027. Four source records consolidated into eight standards covering the complete plugin lifecycle.
