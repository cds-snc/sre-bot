---
id: TASK-145.12
title: >-
  Record cutover: the incident list sheet becomes a write-only projection and
  the sheet import is removed
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-15 18:08'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-27.5
  - TASK-121
  - TASK-145.9
  - TASK-145.5.7
references:
  - 'https://github.com/cds-snc/sre-bot/issues/1690'
parent_task_id: TASK-145
priority: medium
type: task
ordinal: 362000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer E1 of TASK-145. decisions/workplace-systems.md rule 5 and decisions/incident-management.md: no record of truth in a spreadsheet; a surviving sheet is a write-only projection rebuilt from the records.

THIS SLICE
- Every remaining read of the incident list sheet (uniqueness check before declare, listings, postmortem inputs) reads IncidentStore instead; the sheet readers are deleted.
- The Google Sheet import that creates legacy items (incident_folder.create_missing_incidents, reached from the dev load-incidents command in modules/dev/incident.py) is removed with its tests. After it, no code writes a legacy-shape incident item.
- The projection writer is one adapter in core/adapters/ behind a narrow IncidentListProjection interface (append row, update status cell), used by response only and never read. A rebuild command or job regenerates the sheet from the store. It uses the spreadsheets capability if TASK-121 has landed, otherwise the existing provider through a single ignore entry removed by TASK-121.
- /sre incident list reads the store.
- No backfill here: the legacy data upgrade is the TASK-145.5.7 job. After this slice deploys, that job is rerun per environment, dry run then apply, to upgrade any legacy item the sheet import created since its first run.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No code reads the incident list sheet as input to a decision; the projection adapter exposes only append and update-status
- [ ] #2 The sheet import (create_missing_incidents and its caller) is deleted with its tests; no code writes a legacy-shape incident item; the rerun of the TASK-145.5.7 job (dry run then apply, per environment) after deploy is recorded in the notes
- [ ] #3 /sre incident list and the uniqueness check read IncidentStore
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Outline plan grounded at main d2d973ae (2026-10-09); re-ground at pickup (after TASK-145.9). Standalone PR, not stacked: it changes a runtime data path (doc-2). ADDED DEPENDENCY to confirm: a features/ module may not import infrastructure.spreadsheets without a new ignore entry, which migration.md rule 3 forbids, so the projection writer needs the spreadsheets capability (TASK-121) or the legacy writer is called through the frozen module until then.

## Discovered state
- modules/incident/incident_folder.py: append_values on INCIDENT_LIST "Sheet1!A:A" (281), update_spreadsheet_incident_status (314-328), get_incidents_from_sheet (373), create_missing_incidents (487, writes legacy items through db_operations.create_incident), over infrastructure.spreadsheets.get_spreadsheet_provider(). Readers of the sheet: uniqueness check before declare, listings, retro inputs (to enumerate at pickup with rg get_incidents_from_sheet). modules/dev/incident.py load_incidents (43-57) is the only caller of create_missing_incidents; tests/unit/modules/dev/test_dev_incident_handler.py covers it.

## Steps
1. Replace every sheet read with IncidentStore reads (list_active, find_by_conversation); delete get_incidents_from_sheet and its callers' sheet paths.
2. Delete create_missing_incidents, complete_incidents_details if unused after, and the load-incidents dev command with its tests.
3. IncidentListProjection interface in core/api.py (append_row, update_status) with one adapter over capabilities.spreadsheets.api (if TASK-121 landed) and a rebuild job regenerating the sheet from the store with TASK-27.5's full-table read; response calls it from declare and status change.
4. /sre incident list reads the store.
5. After deploy, per environment: rerun the TASK-145.5.7 job, dry run then apply; record the reports in the notes.

## AC traceability
AC1: step 1 -> `rg get_incidents_from_sheet app` empty; projection interface exposes two writes. AC2: step 2 -> `rg create_missing_incidents app` empty; step 5 recorded. AC3: steps 1, 4 -> list and uniqueness tests over the store. AC4: gates.

## Test matrix
Projection: append and status update calls; failure logged and declare continues. Rebuild: sheet regenerated from store items. List and uniqueness over the in-memory IncidentStore.

## Assumptions and doubts
- TASK-121 timing decides the projection adapter's import.

## Size
About 300 production lines, mostly the projection adapter and rebuild, plus deletions.

## Blast radius and rollback
Sheet consumers see the same rows. Revert restores the sheet reads and the import; the upgrade job rerun is idempotent.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14 (TASK-145.5 split): references carry the vendor's own tenant id: the Slack team_id and the Google Workspace customer id from the platform settings added in TASK-145.5.3, never an invented label.

2026-10-15: the legacy backfill moved to the TASK-145.5.7 upgrade job (human); this task removes the sheet import, the last legacy writer, and reruns that job after deploy.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-13 19:59
---
2026-10-13 records/incidents layout decision: the full read of the incidents table for the sheet rebuild uses the full-table read shaped by TASK-27.5 (capped or paginated; a rebuild of an unbounded table may need pagination), not a bounded list assumed in advance. Dependency on TASK-27.5 added.
---
<!-- COMMENTS:END -->
