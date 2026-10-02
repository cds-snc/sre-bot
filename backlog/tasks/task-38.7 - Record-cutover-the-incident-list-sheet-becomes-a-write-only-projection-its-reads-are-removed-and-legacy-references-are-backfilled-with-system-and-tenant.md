---
id: TASK-38.7
title: >-
  Record cutover: the incident list sheet becomes a write-only projection, its
  reads are removed, and legacy references are backfilled with system and tenant
status: To Do
assignee: []
created_date: '2026-10-02 16:43'
labels:
  - migration
  - phase-5
  - incident
milestone: m-5
dependencies:
  - TASK-38.5
  - TASK-38.6
references:
  - decisions/incident-management.md
  - decisions/feature-packages.md
  - decisions/migration.md
  - decisions/workplace-systems.md
parent_task_id: TASK-38
priority: medium
ordinal: 312000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 7 of TASK-38 (cut over). decisions/workplace-systems.md rule 5 and incident-management.md: no record of truth in a spreadsheet; a surviving sheet is a write-only projection rebuilt from storage.

THIS SLICE
- Every remaining read of the incident list sheet (uniqueness check before declare, listings, retro inputs) reads IncidentStore instead; get_incidents_from_sheet and read_values/read_cells callers are deleted.
- The projection writer is one adapter in core/adapters/ behind a narrow IncidentListProjection interface (append row, update status cell), used by lifecycle only; it is never read. A rebuild command or job regenerates the sheet from the store so a failed write is a retry or a rebuild. It uses the spreadsheets capability if TASK-121 has landed, otherwise the existing provider through a single ignore entry removed by TASK-121.
- Backfill: a one-shot, idempotent, safe-to-rerun job converts legacy items (bare channel_id, report_url string, meet_url, retrospective_url, incident_commander/operations_lead ids) into typed references with system and tenant for the configured tenant; dry-run first, counts logged, run in dev then prod. No Terraform change is assumed; record what the backfill needs in the notes.
- /sre incident list reads the store (active and stale).

Who consumes the sheet and what replaces it is the expansion draft under TASK-97; this slice keeps the sheet as a projection so consumers see no change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No code under features/incident/ or app/modules/incident reads the incident list sheet; uniqueness checks and listings read IncidentStore
- [ ] #2 The sheet is written only through IncidentListProjection from lifecycle; a rebuild regenerates it from the store and is idempotent (run twice, same rows)
- [ ] #3 The backfill is a one-shot, idempotent job with a dry-run mode; after it, every stored reference carries system and tenant and no report_url string remains; the run is recorded in the notes with before and after counts
- [ ] #4 A status update that fails to reach the sheet is logged as a projection failure and leaves the record correct; the next rebuild repairs the sheet
- [ ] #5 The legacy_surface suite is green with no assertion change; ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
