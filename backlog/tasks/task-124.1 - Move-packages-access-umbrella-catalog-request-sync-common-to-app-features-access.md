---
id: TASK-124.1
title: >-
  Move packages/access (umbrella: catalog, request, sync, common) to
  app/features/access/
status: To Do
assignee: []
created_date: '2026-09-24 20:01'
labels:
  - plugin-architecture
  - features
milestone: m-7
dependencies:
  - TASK-109
  - TASK-110
  - TASK-111
  - TASK-114
  - TASK-116
  - TASK-118
  - TASK-119
  - TASK-122
  - TASK-30
  - TASK-61
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-124
priority: medium
type: task
ordinal: 267000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Child of TASK-124. access is the reference umbrella (feature-packages.md). It moves last among the shipped features, because it uses almost every infrastructure service. It waits for the approval engine extraction (TASK-61) and the event-bus deletion (TASK-30), so request and sync move in their final shape: no infrastructure.events import, sync handlers async def, interactions/ renamed entrypoints/, and the many extra top-level modules in access/sync (application.py, job_runner.py, presenters.py and others) folded into the layout table.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/<name>/ passes the package-shape check; platforms/ and interactions/ are renamed entrypoints/
- [ ] #2 providers.py resolves contracts from the service registry and imports nothing from infrastructure/ or server/; integrations are imported only from adapters/
- [ ] #3 The entry point targets features.<name> (dotted for subdomains) and has an enablement key; the settings slice's non-secret values live in the TOML files
- [ ] #4 The old packages/ path is deleted; every importer and mock patch string is rewritten; import-linter ignore entries only shrank
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #6 The umbrella __init__.py is empty; every subdomain has a dotted entry point (access.catalog, access.request, access.sync), and the TASK-18 umbrella contract covers features.access with exhaustive = true
- [ ] #7 access/sync handlers are async def, and access/sync uses only layout-table names
<!-- AC:END -->
