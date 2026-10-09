---
id: TASK-145.12
title: >-
  Record cutover: the incident list sheet becomes a write-only projection and
  legacy references are backfilled
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.9
parent_task_id: TASK-145
priority: medium
type: task
ordinal: 362000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer E1 of TASK-145. decisions/workplace-systems.md rule 5 and decisions/incident-management.md: no record of truth in a spreadsheet; a surviving sheet is a write-only projection rebuilt from storage.

THIS SLICE
- Every remaining read of the incident list sheet (uniqueness check before declare, listings, postmortem inputs) reads IncidentStore instead; the sheet readers are deleted.
- The projection writer is one adapter in core/adapters/ behind a narrow IncidentListProjection interface (append row, update status cell), used by response only and never read. A rebuild command or job regenerates the sheet from the store. It uses the spreadsheets capability if TASK-121 has landed, otherwise the existing provider through a single ignore entry removed by TASK-121.
- Backfill: a one-shot, idempotent, safe-to-rerun job converts legacy items (bare channel id, report URL string, meet URL, retrospective URL, IC and OL ids) into typed references with system and tenant for the configured tenant, with severity and timing fields where derivable; dry run first, counts logged, run in dev then prod. What the backfill needs operationally is recorded in the notes.
- /sre incident list reads the store.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No code reads the incident list sheet as input to a decision; the projection adapter exposes only append and update-status
- [ ] #2 The backfill job is idempotent, has a dry-run mode, logs counts and has tests over the legacy item shapes
- [ ] #3 /sre incident list and the uniqueness check read IncidentStore
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
