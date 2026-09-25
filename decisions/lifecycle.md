---
status: Accepted
date: 2026-07-06
applies: target
scope: Application startup phases, readiness, and shutdown.
---

# Application Lifecycle

## Context

Composition order matters: configuration before services, services before plugins, extension points filled before the capabilities that own them initialize, everything before traffic. The app runs as two or more replicas ([plugin-architecture.md](plugin-architecture.md)).

Current code (`app/server/lifespan.py`):
- Loads settings slices and logs their keys, warms JWKS (a missing `ISSUER_CONFIG` logs a warning and continues) and the directory provider.
- Discovers plugins by walking `packages/` and `modules/` (`auto_discover_plugins`), which logs and skips a package that fails to import.
- Collects i18n resources through `register_i18n_resources`, then initializes the translator strictly; failure aborts boot.
- Calls `register_slack_commands`, `register_routes` and `startup_warmup`; features construct their services lazily or inside `startup_warmup`. `access/request` and `access/sync` subscribe to in-process events there.
- Registers legacy `modules/` handlers by hand, starts scheduled tasks only when `ENVIRONMENT == "production"` (Tier-2 jobs take a lease from the idempotency store), then starts Socket Mode.
- On shutdown, stops scheduled tasks, then the Slack provider.

Phases are logged with a `phase` field, but there is no single ordered sequence, no eager service validation, and plugin load errors are not fatal.

## Decision

One ASGI lifespan with ordered phases, each logged with its name:

1. **Configuration.** Load the base configuration file and the one for `ENVIRONMENT`, plus secrets, and validate every settings slice ([configuration.md](configuration.md)). Invalid or missing configuration fails boot here.
2. **Core services.** Register a factory per `contracts` Protocol in the svcs registry, then resolve each once and run its health check ([dependency-injection.md](dependency-injection.md)).
3. **Plugin loading.** Read the entry points declared in `pyproject.toml` ([plugins.md](plugins.md)). Skip, before registration, every plugin that the environment's configuration file disables. Register the rest; an import error is fatal.
4. **Extension points.** For each capability, in its declared order, call its hookspecs once to collect strategy objects (an `ApprovalPolicy`, an alert-action handler), then initialize the capability with them. A capability never initializes with an extension point still unfilled.
5. **Feature registration.** Registration hookspecs fire: routes mount, platform handlers attach, jobs register with the scheduler. Registries freeze at `yield`.
6. **Transport.** HTTP serves; Socket Mode connects; the scheduler starts.
7. **Shutdown.** Reverse order, each step with a bounded budget, completing inside the platform's grace window (30 s on ECS; `terminationGracePeriodSeconds` on Kubernetes and OpenShift).

**Fail fast.** Any exception before `yield` aborts boot. No degraded starts except those a record explicitly defines (JWKS issuer gaps, [security.md](security.md)).

**Every replica runs the same lifespan.** No phase assumes it is the only process: nothing keeps shared state in memory, and a scheduled job runs once across replicas by taking a lease from the coordination contract before each run ([reliability.md](reliability.md)).

**Readiness** means all phases completed. Probe endpoints and their policy are defined in [health-checks.md](health-checks.md). Deploy validation watches readiness, not logs ([cloud-portability.md](cloud-portability.md)).

**Crash-only discipline.** The process must tolerate being killed at any phase; recovery is restart, not repair. [reliability.md](reliability.md) makes the side effects safe.

## Consequences

- "Why isn't my service available?" is answerable from phase logs; a hang is attributable to a phase.
- Eager validation trades slower boot for no construction failures mid-request.
- Strategy collection before capability initialization makes a missing policy a boot failure, not a runtime error.
- Cost: every service and plugin must be constructible at boot in every environment, including CI.

## Checks

- Lifespan test: phases log in order; a poisoned factory or plugin aborts before `yield`.
- Boot test: a plugin disabled in configuration is never registered; every extension point is filled before its capability initializes.
- Readiness flips only after `yield`; shutdown completes within budget under test.
- Review: no scheduled job runs without a lease.

## Migration

Tickets: TASK-58 (coordination contract and leases). Tickets to create for the service registry and plugin loading are listed in [plugin-architecture.md](plugin-architecture.md).

Tolerated until closed:
- plugin discovery by filesystem walk, with import errors logged and skipped;
- services built lazily or in `startup_warmup` hookimpls instead of an eager registry phase;
- in-process event subscriptions registered in `startup_warmup` by `access/request` and `access/sync`;
- scheduled tasks gated on `ENVIRONMENT == "production"` and started from `jobs/scheduled_tasks.py`, with leases from the idempotency store;
- legacy `modules/` handlers registered by hand after feature registration.

**Changes:**
- 2026-09-24: phases aligned with plugin-architecture (config-file enablement, registry validation, extension-point collection, multi-replica); `applies` corrected to `target`.
