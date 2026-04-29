---
adr_id: ADR-0005
title: "Application Initialization Lifecycle"
status: Superseded
decision_type: Principle
tier: Tier-1
date_created: unknown
last_updated: 2026-04-29
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by:
  - ADR-0046
related_records:
  - ADR-0009
  - ADR-0010
  - ADR-0011
  - ADR-0012
  - ADR-0013
  - ADR-0014
  - ADR-0015
  - ADR-0016
related_packages: []
review_state: stale
---
# Application Initialization Lifecycle

High-level initialization for FastAPI application using lifespan context manager.

See the dedicated lifecycle ADRs listed below for detailed specifications.

---

## Current Implementation (Legacy)

`app/main.py` uses `app.add_event_handler("startup", ...)` for initialization.
FastAPI recommends lifespan and deprecates startup/shutdown events when lifespan is provided.

---

## 7-Phase Initialization Sequence

1. **Configuration**: Load Settings singleton, configure logging
2. **Infrastructure**: Initialize core services, plugin managers
3. **Providers**: Discover and activate (Groups, Commands, Platforms)
4. **Features**: Register event handlers, platform plugins
5. **Commands**: Register commands with platforms
6. **Socket Mode**: Start Slack WebSocket (daemon thread, non-blocking)
7. **Background**: Scheduled jobs (production only)

---

## Key Principles

- ✅ Single Settings instance via `@lru_cache`
- ✅ Sequential phase execution
- ✅ Fail fast on critical errors
- ✅ Immutable registries after startup
- ✅ Structured logging per phase
- ✅ Graceful shutdown in reverse order
- ✅ Lifespan-only startup/shutdown (no mixing with startup/shutdown events)
- ✅ Lifespan teardown runs after connections close and background work finishes

---

## Anti-patterns

- ❌ New initialization logic added via `app.add_event_handler("startup", ...)`
- ❌ Mixing `lifespan` with startup/shutdown events
- ❌ Skipping or reordering phases
- ❌ Registering providers after startup

---

## Detailed Specifications

Detailed phase-level records are listed in frontmatter under `related_records`.
