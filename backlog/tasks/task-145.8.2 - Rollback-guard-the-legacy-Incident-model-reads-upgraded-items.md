---
id: TASK-145.8.2
title: 'Rollback guard: the legacy Incident model reads upgraded items'
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - legacy
dependencies: []
parent_task_id: TASK-145.8
priority: medium
type: task
ordinal: 507000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L5r (approved 2026-11-09, OQ18): app/models/incidents.py Incident takes extra="ignore" and renders an int severity as sev-N, so reverting any reader cutover keeps the restored legacy reader working on items upgraded by the rebuilt writers (AWS rollback-safety practice). Never used for dual-write; deleted with the model by TASK-145.7's declare cutover. Merges before the first reader cutover.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A legacy Incident built from an upgraded (marker 2) item validates, with severity rendered as sev-N (tested); the PR body states it is a rollback guard deleted with the model
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
