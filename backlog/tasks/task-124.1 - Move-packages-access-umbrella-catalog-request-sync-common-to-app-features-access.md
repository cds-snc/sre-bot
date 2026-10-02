---
id: TASK-124.1
title: >-
  Move packages/access (umbrella: catalog, request, sync, common) to
  app/features/access/
status: To Do
assignee: []
created_date: '2026-09-24 20:01'
updated_date: '2026-10-02 00:47'
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

Added 2026-10-01 (amended decisions/feature-packages.md, umbrella rules 4 and 5): common/ does no I/O. access/common today reads runtime-config files (config/loaders.py) and holds a cached provider (providers.py). Both move to access/core/, which the three subdomains import only through core/api.py. The pure types (settings tree, AccessRuntimeConfig and its dataclasses, ManagedGroupPolicy, naming, event names while they exist) stay in common/. The subdomains stay independent siblings; nothing else about their boundaries changes.
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
- [ ] #8 access/common does no I/O: the runtime-config loaders and their provider live in access/core/ and are imported only through core/api.py; core/ has no entrypoints/, no hookimpls and no entry point; the umbrella layers contract lists core between the subdomains and common
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From TASK-136 (2026-10-02): each access subdomain declares its service Protocol twice, once in the service module (AccessRequestWorkflow, EntitlementCatalog, AccessSynchronizer after TASK-136.3) and once as a private route-local twin in interactions/http.py (_AccessRequestWorkflow, _EntitlementCatalog, _AccessSynchronizer). The catalog and sync twins are method-for-method identical; the request twin omits advance_from_sync_result. When this task rewrites interactions/ into entrypoints/, collapse each twin onto its subdomain's public Protocol (or decide to keep the narrower request one). This stays inside each subdomain and is not an access/core item: core/ admits only what two or more subdomains consume.

Caveat on the twin collapse: the type-model-boundaries skill's Protocol Alignment Pattern explicitly allows a narrower route-local Protocol beside the shared one, so the twins follow a documented pattern. Collapsing them means deciding that pattern no longer applies to access (and updating the skill), not just deleting duplicates.
<!-- SECTION:NOTES:END -->
