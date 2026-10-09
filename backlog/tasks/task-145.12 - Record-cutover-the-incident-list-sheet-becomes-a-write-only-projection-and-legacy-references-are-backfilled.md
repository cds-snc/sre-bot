---
id: TASK-145.12
title: >-
  Record cutover: the incident list sheet becomes a write-only projection and
  legacy references are backfilled
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 18:22'
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Outline plan grounded at main d2d973ae (2026-10-09); re-ground at pickup (after TASK-145.9). Standalone PR, not stacked: it changes a runtime data path (doc-2). ADDED DEPENDENCY to confirm: a features/ module may not import infrastructure.spreadsheets without a new ignore entry, which migration.md rule 3 forbids, so the projection writer needs the spreadsheets capability (TASK-121) or the legacy writer is called through the frozen module until then.

## Discovered state
- modules/incident/incident_folder.py: append_values on INCIDENT_LIST "Sheet1!A:A" (281), update_spreadsheet_incident_status (314-328), get_incidents_from_sheet (373), over infrastructure.spreadsheets.get_spreadsheet_provider(). Readers of the sheet: uniqueness check before declare, listings, retro inputs (to enumerate at pickup with rg get_incidents_from_sheet).
- Legacy items carry bare channel_id, report_url, meet_url, retrospective_url, incident_commander and operations_lead strings (models/incidents.py).

## Steps
1. Replace every sheet read with IncidentStore reads (list_active, find_by_conversation); delete get_incidents_from_sheet and its callers' sheet paths.
2. IncidentListProjection interface in core/api.py (append_row, update_status) with one adapter over capabilities.spreadsheets.api (if TASK-121 landed) and a rebuild job regenerating the sheet from the store; response calls it from declare and status change.
3. Backfill: a one-shot idempotent job (bin or management command) converting legacy items to typed references for the configured tenant, mapping severity and timing fields where derivable; dry-run mode logging counts; run in dev then prod; operational notes in the task.
4. /sre incident list reads the store.

## AC traceability
AC1: step 1 -> `rg get_incidents_from_sheet app` empty; projection interface exposes two writes. AC2: step 3 -> backfill tests over each legacy item shape, idempotency and dry run. AC3: steps 1, 4 -> list and uniqueness tests over the store. AC4: gates.

## Test matrix
Projection: append and status update calls; failure logged and declare continues. Backfill: item with every field; "Unknown" times; missing roles; already-converted item unchanged on rerun; dry run writes nothing.

## Assumptions and doubts
- TASK-121 timing decides the projection adapter's import; add the dependency when the plan is approved.
- No Terraform change is assumed for the backfill (same table); confirm IAM allows UpdateItem from the job role.

## Size
About 350 production lines plus the backfill job.

## Blast radius and rollback
Sheet consumers see the same rows; a wrong backfill is rerunnable (idempotent) and the previous item fields are kept, not deleted. Revert restores the sheet reads.
<!-- SECTION:PLAN:END -->
