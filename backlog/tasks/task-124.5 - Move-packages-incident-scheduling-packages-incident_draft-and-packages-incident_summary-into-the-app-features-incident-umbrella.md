---
id: TASK-124.5
title: >-
  Move packages/incident/scheduling, packages/incident_draft and
  packages/incident_summary into the app/features/incident/ umbrella
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
  - TASK-114
  - TASK-118
  - TASK-120
  - TASK-25.10
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
Child of TASK-124. This takes over the relocation part of TASK-38 (its AC #5 and #8): packages/incident_draft -> features/incident/draft, packages/incident_summary -> features/incident/summary, packages/incident/scheduling -> features/incident/scheduling, with dotted entry-point names (incident.draft, incident.summary, incident.scheduling). These are import-path and entry-point-name changes with no runtime surface change. Sweep every unittest.mock patch string, which fails at patch time, not import time. Waits for TASK-25.10 (OpenAI Summarizer out of the vendor package) and the drive capability (TASK-120), so the subdomains move in their final shape.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/<name>/ passes the package-shape check; platforms/ and interactions/ are renamed entrypoints/
- [ ] #2 providers.py resolves contracts from the service registry and imports nothing from infrastructure/ or server/; integrations are imported only from adapters/
- [ ] #3 The entry point targets features.<name> (dotted for subdomains) and has an enablement key; the settings slice's non-secret values live in the TOML files
- [ ] #4 The old packages/ path is deleted; every importer and mock patch string is rewritten; import-linter ignore entries only shrank
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #6 features/incident/__init__.py is empty; incident.draft, incident.summary and incident.scheduling are dotted entry points; no packages/incident* directory remains; the TASK-18 umbrella contract covers features.incident with exhaustive = true
<!-- AC:END -->
