---
id: TASK-145.7.12
title: Legacy upgrade job maps the report's Drive roles into the record
status: To Do
assignee: []
created_date: '2026-11-16T19:34:00Z'
labels:
  - incident
  - migration
dependencies:
  - TASK-145.8.5.1
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 526000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L side PR (doc-11 row 18.L7c, before 18.L8). Created 2026-11-16 (human, TASK-145.8.5 OQ7): legacy roles live only in the report's Drive properties ic_id/ol_id (no legacy writer sets the item's incident_commander/operations_lead), so the backfill reads them through TASK-145.8.5.1's legacy-only core adapter and the shared per-item upgrade plan maps them as optional values (Migration rules 2 and 7) on items with no role on the record. Must merge before the job's apply (TASK-145.7.8). TASK-145.13 deletes it with the bridge. Plan in full at pickup.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The job reads each item's report Drive properties through the legacy roles adapter and the shared upgrade plan sets the record's incident commander and operations lead from them when the item holds no role; a missing report or unreadable properties is counted as dropped (rule 7) and never fails the run
- [ ] #2 The run report counts roles mapped and dropped per item; a rerun changes nothing (marker rule 4)
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
