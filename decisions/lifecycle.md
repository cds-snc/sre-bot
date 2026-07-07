---
status: Accepted
date: 2026-07-06
applies: now
scope: Application startup phases, readiness, and shutdown.
---

# Application Lifecycle

## Context

Composition order matters: settings before clients, clients before services, services before feature registration, everything before traffic. The phased-lifespan design from the old corpus was sound and implemented; this record carries it forward condensed.

## Decision

One ASGI lifespan with ordered phases, each logged:

1. **Configuration** — settings providers load and validate; missing config fails boot here.
2. **Infrastructure composition** — the provider registry is invoked eagerly ([dependency-injection.md](dependency-injection.md)); clients, services, and transports construct.
3. **Plugin discovery** — feature plugins register ([plugins.md](plugins.md)); failure is fatal.
4. **Feature activation** — registration hookspecs fire: routes mount, platform handlers attach, event subscribers and jobs register. Registries freeze at `yield`.
5. **Transport** — HTTP binds; Socket Mode connects; jobs start.
6. **Shutdown** — reverse order, each step with a bounded budget, completing inside the platform's grace window (30 s on ECS; `terminationGracePeriodSeconds` on K8s/OpenShift).

**Fail fast:** any exception before `yield` aborts boot. No degraded starts except those a record explicitly defines (JWKS issuer gaps, [security.md](security.md)).

**Readiness** = all phases complete (`/health/readiness`); **liveness** = process responsive (`/health/liveness`). Health endpoints are exempt from auth and rate limits. Deploy validation watches readiness, not logs ([cloud-portability.md](cloud-portability.md)).

**Crash-only discipline:** the process must tolerate being killed at any phase; recovery is restart, not repair ([reliability.md](reliability.md) makes the side-effects safe).

## Consequences

- "Why isn't my service available?" is answerable from phase logs; a hang is attributable to a phase.
- Eager phase-2 composition trades slower boot for no mid-request construction surprises.

## Checks

- Lifespan test: phases log in order; poisoned provider/plugin aborts before `yield`.
- Readiness flips only after `yield`; shutdown completes within budget under test.
