---
id: TASK-145.12
title: >-
  Record cutover: the incident list sheet becomes a write-only projection and
  the sheet import is removed
status: To Do
assignee: []
created_date: 2026-10-09 16:43
updated_date: '2026-10-28T17:26:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-27.5
  - TASK-121
  - TASK-145.9
  - TASK-145.5.7
  - TASK-111.10
references:
  - https://github.com/cds-snc/sre-bot/issues/1690
parent_task_id: TASK-145
priority: medium
type: task
ordinal: 362000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer E1 of TASK-145. decisions/workplace-systems.md rule 5 and decisions/incident-management.md: no record of truth in a spreadsheet; a surviving sheet is a write-only projection rebuilt from the records.

THIS SLICE
- Every remaining read of the incident list sheet (listings, postmortem inputs) reads IncidentStore instead, and the duplicate-row check before the declare's append is removed; the sheet readers are deleted.
- The Google Sheet import that creates legacy items (incident_folder.create_missing_incidents, reached from the dev load-incidents command in modules/dev/incident.py) is removed with its tests. After it, no code writes a legacy-shape incident item.
- The projection writer is one adapter in core/adapters/ behind a narrow IncidentListProjection interface (append row, update status cell), used by response only and never read. A rebuild command or job regenerates the sheet from the store. It uses the spreadsheets capability (TASK-121).
- /sre incident list reads the store.
- No backfill here: the legacy data upgrade is the TASK-145.5.7 job. After this slice deploys, that job is rerun per environment, dry run then apply, to upgrade any legacy item the sheet import created since its first run.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No code reads the incident list sheet as input to a decision; the projection adapter exposes only append and update-status
- [ ] #2 The sheet import (create_missing_incidents and its caller) is deleted with its tests; no code writes a legacy-shape incident item; the rerun of the TASK-145.5.7 job (dry run then apply, per environment) after deploy is recorded in the notes
- [ ] #3 /sre incident list (active and stale) reads IncidentStore.list_open over the open index; the sheet's duplicate-row check before the append is removed because the declare appends the projection row once inside its idempotent write; the rebuild job is the only whole-table read, through RecordStore.read_all with max_items from INCIDENT_CORE__FULL_READ_MAX_ITEMS (decisions/cloud-portability.md contract 4: a whole-table read is never a lookup or a listing)
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #5 The incident list sheet id moves from the interim [google_resources] table into the incident slice's table in the configuration files, and GoogleResourcesConfig stops exposing it
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Outline plan grounded at main d2d973ae (2026-10-09); re-ground at pickup (after TASK-145.9). Standalone PR, not stacked: it changes a runtime data path (doc-2). ADDED DEPENDENCY to confirm: a features/ module may not import infrastructure.spreadsheets without a new ignore entry, which migration.md rule 3 forbids, so the projection writer needs the spreadsheets capability (TASK-121) or the legacy writer is called through the frozen module until then.

## Discovered state
- modules/incident/incident_folder.py: append_values on INCIDENT_LIST "Sheet1!A:A" (281), update_spreadsheet_incident_status (314-328), get_incidents_from_sheet (373), create_missing_incidents (487, writes legacy items through db_operations.create_incident), over infrastructure.spreadsheets.get_spreadsheet_provider(). Readers of the sheet: the duplicate-row check before the append in modules/incident/core.py (about line 251, matches channel_id or channel slug), listings, retro inputs (to enumerate at pickup with rg get_incidents_from_sheet). modules/dev/incident.py load_incidents (43-57) is the only caller of create_missing_incidents; tests/unit/modules/dev/test_dev_incident_handler.py covers it.
- Legacy /sre incident list (modules/incident/incident_helper.py handle_list): `active` is a placeholder, `stale` lists open incidents older than 14 days without activity. Both are open-incident listings.

## Steps
1. Replace every sheet read with IncidentStore reads: listings use list_open (open index), the per-channel lookup uses find_by_conversation; delete get_incidents_from_sheet and its callers' sheet paths. The duplicate-row check is removed: the declare appends the projection row once, inside its idempotent write.
2. Delete create_missing_incidents, complete_incidents_details if unused after, and the load-incidents dev command with its tests.
3. IncidentListProjection interface in core/api.py (append_row, update_status) with one adapter over capabilities.spreadsheets.api (if TASK-121 landed) and a rebuild job regenerating the sheet from the store with RecordStore.read_all (TASK-27.5), max_items from INCIDENT_CORE__FULL_READ_MAX_ITEMS (added by TASK-145.5.7); past the cap the rebuild fails without writing; response calls the projection from declare and status change.
4. /sre incident list (active and stale) reads IncidentStore.list_open; stale filters on last activity client-side over the open incidents.
5. After deploy, per environment: rerun the TASK-145.5.7 job, dry run then apply; record the reports in the notes.

## AC traceability
AC1: step 1 -> `rg get_incidents_from_sheet app` empty; projection interface exposes two writes. AC2: step 2 -> `rg create_missing_incidents app` empty; step 5 recorded. AC3: steps 1, 3, 4 -> list tests over list_open, no duplicate-row check, rebuild over read_all including the over-cap failure. AC4: gates.

## Test matrix
Projection: append and status update calls; failure logged and declare continues; a replayed declare appends once. Rebuild: sheet regenerated from store items; over-cap read fails and writes nothing. List active and stale over the in-memory IncidentStore.

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

2026-10-20 (TASK-27.5 planning): AC3 rewritten. The whole-table read rule (decisions/cloud-portability.md contract 4) makes listings an index read (list_open) and removes the sheet duplicate-row check; only the rebuild uses read_all.

2026-10-28 (TASK-111.14): new incident list rows hold the channel as Slack's deep link (slack.com/app_redirect?channel=<id>&team=<team_id>), older rows hold gcdigital.slack.com/archives/<id>; modules/incident/incident_folder.channel_id_from_link reads both until the sheet import is removed here.
<!-- SECTION:NOTES:END -->
