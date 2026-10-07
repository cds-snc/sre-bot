---
id: TASK-140.7
title: >-
  Retire the legacy /sre incident updates command and the incident_updates
  attribute
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-07 15:17'
labels:
  - incident
dependencies:
  - TASK-140.6
  - TASK-140.8
parent_task_id: TASK-140
priority: medium
type: chore
ordinal: 326000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per decisions/migration.md: pin the surface, cut over to /sre incident status-update, remove the legacy registration and the incident_updates read and write paths in modules/incident, and update the legacy_surface INVENTORY. Legacy /sre incident status (internal lifecycle state) stays until TASK-38.4.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 /sre incident updates answers with a pointer to /sre incident status-update, pinned in legacy_surface before and after
- [ ] #2 No code reads or writes incident_updates; INVENTORY.md rows updated
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
