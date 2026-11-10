---
id: TASK-145.12.2
title: >-
  Incident list becomes write-only: list reads the open index; sheet import and
  dev incident commands deleted
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T16:37:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.7.10
  - TASK-145.9.2
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.12
priority: medium
type: feature
ordinal: 520000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L11 (outline in TASK-145.12's plan). /sre incident list active and stale read IncidentStore.list_open; the duplicate-row check is removed; get_incidents_from_sheet, create_missing_incidents and the dev incident commands are deleted with their callers, registrations and tests (the last legacy writers). After deploy the human reruns the job (dry run, then apply) and records it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No code reads the sheet; list reads list_open; no code writes a legacy-shape item; no module imports modules.incident.db_operations for incident data (checks parent ACs #1-#3, #7, #8)
- [ ] #2 The job rerun reports are recorded in the notes (parent AC #2)
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10: after this task deploys, the legacy upgrade job reruns (dry_run, then apply; README Rerun rule) before TASK-145.13 deletes it; items written by a legacy writer after the TASK-145.7.8 run have no marker and no binding until then.
<!-- SECTION:NOTES:END -->
