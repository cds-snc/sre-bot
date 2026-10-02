---
id: TASK-124.5
title: >-
  Move packages/incident/ (core, scheduling and the reshaped draft and summary
  subdomain) into the app/features/incident/ umbrella
status: To Do
assignee: []
created_date: '2026-09-24 20:01'
updated_date: '2026-10-02 16:59'
labels:
  - plugin-architecture
  - features
milestone: m-7
dependencies:
  - TASK-109
  - TASK-110
  - TASK-114
  - TASK-118
  - TASK-120
  - TASK-25.10
  - TASK-134
  - TASK-135
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
  - decisions/incident-management.md
parent_task_id: TASK-124
priority: medium
type: task
ordinal: 271000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Child of TASK-124. Rescoped 2026-10-01 to the amended decisions/feature-packages.md and 2026-10-02 to decisions/incident-management.md (TASK-97): incident_draft and incident_summary are no longer moved as two subdomains. TASK-135 first reshapes them into the scribe subdomain over packages/incident/core, and TASK-134 moves the generic answer parsing into the text-generation capability. This task then moves the incident umbrella as it stands: packages/incident/ -> features/incident/, with core/ and the scribe subdomain TASK-135 created, and the dotted entry-point name incident.scribe. core/ gets no entry point.

The adapter-only packages packages/incident/documents, drive, meet and scheduling (no hookimpls, built for modules/incident) move with the umbrella as they are, with no entry point; TASK-38.2, TASK-38.3 and TASK-38.6 fold them into core/adapters/, lifecycle/adapters/ and retrospective/adapters/ afterwards. The umbrella layers contract keeps them as independent siblings above core until then.

These are import-path and entry-point-name changes with no runtime surface change. Sweep every unittest.mock patch string, which fails at patch time, not import time. Waits for TASK-135, TASK-134, TASK-25.10 (text-generation capability) and the drive capability (TASK-120), so the umbrella moves in its final shape. TASK-38.1 builds on the result.

This replaces the relocation part of TASK-38 (its former AC #5 and #8).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/<name>/ passes the package-shape check; platforms/ and interactions/ are renamed entrypoints/
- [ ] #2 providers.py resolves contracts from the service registry and imports nothing from infrastructure/ or server/; integrations are imported only from adapters/
- [ ] #3 The entry point targets features.<name> (dotted for subdomains) and has an enablement key; the settings slice's non-secret values live in the TOML files
- [ ] #4 The old packages/ path is deleted; every importer and mock patch string is rewritten; import-linter ignore entries only shrank
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #6 features/incident/__init__.py is empty; every subdomain has a dotted incident.<subdomain> entry point and core/ and common/ have none; no packages/incident* directory remains; the umbrella layers contract covers features.incident with the subdomains as independent siblings above core above common, and exhaustive = true
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 16:59
---
2026-10-02: packages/incident/scheduling becomes the calendar capability (TASK-138). If TASK-138 lands before this move, scheduling is already gone; otherwise it moves with the umbrella as an adapter-only sibling and TASK-138 deletes it afterwards.
---
<!-- COMMENTS:END -->
