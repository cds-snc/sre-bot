---
id: TASK-106
title: >-
  Create app/contracts/ and move OperationResult, OperationStatus and the
  error-code registry into it
status: To Do
assignee: []
created_date: '2026-09-24 19:57'
labels:
  - plugin-architecture
  - contracts
milestone: m-7
dependencies:
  - TASK-18
  - TASK-105
references:
  - decisions/plugin-architecture.md
  - decisions/operation-result.md
  - decisions/outbound-clients.md
priority: high
type: task
ordinal: 246000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md: app/contracts/ is the public plugin API. It holds hookspecs, the core-service Protocols and shared types (OperationResult, OperationStatus, identifiers, an actor reference), contains no implementation and imports only the standard library, typing and pluggy markers. decisions/operation-result.md moves OperationResult there so every layer, integrations included, can import it.

This is the first contracts move, and it creates the package. It is mechanical: no behaviour change (the envelope fix lands first).

No shims. app/infrastructure/operations/ is deleted in the same change, with no re-export, and every importer is rewritten: packages, modules, integrations, infrastructure, server, jobs, api, tests, and unittest.mock patch-target strings. A per-layer split would need a temporary re-export, so a single codemod PR is the expected shape; the planner confirms it against the size gate. Record the file count and why a split would leave a shim.

The same PR applies the cascade: decisions/outbound-clients.md drops its tolerance for integrations importing infrastructure.operations, and the import-linter ignore entries that existed only for that import are removed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/contracts/ exists and imports nothing from the app, enforced by the TASK-18 contracts forbidden contract
- [ ] #2 OperationResult, OperationStatus and the error-code registry live in app/contracts/; app/infrastructure/operations/ is deleted with no re-export or alias
- [ ] #3 grep finds no infrastructure.operations import or patch-target string anywhere under app/
- [ ] #4 The import-linter ignore entries that existed only for infrastructure.operations imports are removed, and the ruff isort known-first-party list includes contracts, features and capabilities
- [ ] #5 decisions/outbound-clients.md and decisions/operation-result.md no longer list infrastructure/operations as a tolerated divergence
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
