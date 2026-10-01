---
id: TASK-124.5
title: >-
  Move packages/incident/ (core, scheduling and the reshaped draft and summary
  subdomain) into the app/features/incident/ umbrella
status: To Do
assignee: []
created_date: '2026-09-24 20:01'
updated_date: '2026-10-01 14:06'
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
parent_task_id: TASK-124
priority: medium
type: task
ordinal: 271000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Child of TASK-124. Rescoped 2026-10-01 to the amended decisions/feature-packages.md: incident_draft and incident_summary are no longer moved as two subdomains. TASK-135 first reshapes them into one incident subdomain over packages/incident/core, and TASK-134 moves the generic answer parsing into the text-generation capability. This task then moves the incident umbrella as it stands: packages/incident/ -> features/incident/, with core/, scheduling/ and the subdomain TASK-135 created, and dotted entry-point names for the subdomains (incident.scheduling and the name TASK-135 chose). core/ and common/ get no entry point.

These are import-path and entry-point-name changes with no runtime surface change. Sweep every unittest.mock patch string, which fails at patch time, not import time. Waits for TASK-135, TASK-134, TASK-25.10 (text-generation capability) and the drive capability (TASK-120), so the umbrella moves in its final shape.

The adapter-only packages packages/incident/documents, drive and meet move with the umbrella in whatever position TASK-135 or TASK-38 left them (folded into core/, or still separate).

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
