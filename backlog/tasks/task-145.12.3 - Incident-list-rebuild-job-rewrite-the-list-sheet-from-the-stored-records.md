---
id: TASK-145.12.3
title: 'Incident list rebuild job: rewrite the list sheet from the stored records'
status: To Do
assignee: []
created_date: '2026-11-16T13:16:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.12.2
references:
  - decisions/workplace-systems.md
  - decisions/incident-management.md
parent_task_id: TASK-145.12
priority: medium
type: feature
ordinal: 522000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L (doc-11 row 18.L11b, after 145.12.2). Created 2026-11-16 from the TASK-145.12.1 rulings (R1, R6): decisions/workplace-systems.md rule 5 makes the list sheet a rebuildable projection keyed by incident id, and TASK-145.12 AC #3 names a rebuild job, but no subtask built it. The response subdomain registers a job with a lease; it reads every incident through RecordStore.read_all bounded by [incident_core] full_read_max_items (the only whole-table read, cloud-portability.md contract 4), writes the full sheet (rows from core/adapters/list_rows.py) to a new tab, validates it, then swaps it in (Azure Materialized View pattern). It fills column F on every row; after its first production run the channel-id fallback in core/adapters/google_sheets.py is deleted. It is the repair path for projection-write failures and racing appends, and the hook for doc-15 needs (embargo codenames 165.3, drill exclusion 165.7). Assumption to verify at planning with the sheet's users: nobody edits rows by hand (a rebuild overwrites them).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A registered, leased job rewrites the list sheet from RecordStore.read_all (bounded by full_read_max_items) into a new tab, validates it and swaps it in; a failed run leaves the current sheet untouched
- [ ] #2 Every rebuilt row carries the incident id in column F; after the first production run is recorded in the notes, the channel-id fallback in core/adapters/google_sheets.py and its tests are deleted
- [ ] #3 The run reports (per environment, dry run then apply) are recorded in the notes; whether anyone edits the sheet by hand is confirmed with its users before the first apply
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
