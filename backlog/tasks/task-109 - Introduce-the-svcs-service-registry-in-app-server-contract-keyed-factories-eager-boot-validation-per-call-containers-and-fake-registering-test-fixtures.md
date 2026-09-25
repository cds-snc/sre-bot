---
id: TASK-109
title: >-
  Introduce the svcs service registry in app/server/: contract-keyed factories,
  eager boot validation, per-call containers and fake-registering test fixtures
status: To Do
assignee: []
created_date: '2026-09-24 19:58'
updated_date: '2026-09-25 15:00'
labels:
  - plugin-architecture
  - dependency-injection
milestone: m-7
dependencies:
  - TASK-108
  - TASK-58
  - TASK-92
references:
  - decisions/dependency-injection.md
  - decisions/lifecycle.md
  - decisions/testing.md
  - 'https://svcs.hynek.me/'
priority: high
type: feature
ordinal: 251000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/dependency-injection.md replaces cached module-level provider functions with a type-keyed svcs registry. This is the "separate ticket, still to create" its Migration names. It supersedes TASK-29 (an lru_cache @provider registry with a global cache-clearing fixture), which built the pattern the record now replaces.

Decision points implemented here:
- At startup app/server/ registers one factory per contracts Protocol (storage, coordination to start). The Protocol is the key; the concrete class appears only in the host's registration code.
- Eager validation: lifespan resolves every registered service once from a startup container. The boot check is construction plus static validation of the settings slice, with no network I/O (decisions/dependency-injection.md, lifecycle.md phase 2). A missing setting or a failing constructor aborts boot before yield. A factory may register an svcs ping for diagnostics; pings never run at boot or behind the platform health checks.
- HTTP routes use the svcs FastAPI integration (DepContainer, await services.aget(Protocol)).
- Slack handlers, webhook consumers and jobs open a container per invocation and close it when the invocation ends.
- Only entry points touch a container. Services receive their dependencies through their constructor.
- Tests build a registry and register Protocol-conforming fakes. No test clears global caches.
- Adds the import-linter forbidden contract "nothing outside server/ imports provider modules or infrastructure implementations", seeded with today's violations as ignore entries.

Out of scope: moving each consumer off its infrastructure get_* provider. Each package does that when it moves to app/features/ or app/capabilities/, so no package runs half on providers and half on the registry. TASK-92 decided the boot-check rule (2026-09-25): construction and static validation only; no vendor or dependency call at boot or in readiness.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 svcs is a runtime dependency; app/server/ registers a factory per contracts Protocol it covers, and concrete class names appear only in that registration code
- [ ] #2 A registered factory that raises aborts lifespan before yield (boot test)
- [ ] #3 An HTTP route resolves a service through the svcs FastAPI integration, and a Slack handler and a job each resolve through a per-invocation container that is closed afterwards (tests)
- [ ] #4 A test fixture registers fakes against contracts Protocols; no fixture clears provider caches for registry-resolved services
- [ ] #5 The import-linter forbidden contract for provider modules exists, with current violations as ignore entries and unmatched alerting on
- [ ] #6 decisions/dependency-injection.md Migration names this ticket; ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #7 Boot test: resolving every registered service opens no outbound connection (socket.connect spy)
<!-- AC:END -->
