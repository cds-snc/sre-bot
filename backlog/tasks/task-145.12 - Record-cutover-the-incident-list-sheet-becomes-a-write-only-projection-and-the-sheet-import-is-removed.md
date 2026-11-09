---
id: TASK-145.12
title: >-
  Record cutover: the incident list sheet becomes a write-only projection and
  the sheet import is removed
status: To Do
assignee: []
created_date: 2026-10-09 16:43
updated_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-27.5
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
- [ ] #3 /sre incident list (active and stale) reads IncidentStore.list_open over the open index; the sheet's duplicate-row check before the append is removed because the declare appends the projection row once inside its idempotent write; the rebuild job is the only whole-table read, through RecordStore.read_all with max_items from [incident_core] full_read_max_items (features/incident/common/settings.py, added by TASK-145.5.7) (decisions/cloud-portability.md contract 4: a whole-table read is never a lookup or a listing)
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #5 The projection reads the incident list sheet id from [incident_core] list_sheet_id and every subdomain that writes the projection states it as required when it registers (decisions/plugins.md: a plugin states what it requires by resolving it; boot fails naming the key when it is empty). The key itself is already in place (TASK-111.10.3: non-public, declared empty in base.toml, value from the environment only)
- [ ] #6 The list-sheet projection writer is an incident-owned adapter calling integrations/google_workspace directly; nothing in the incident umbrella uses infrastructure/spreadsheets (TASK-169 ruling, 2026-11-05 (human))
- [ ] #7 No module imports modules.incident.db_operations or packages.aws_platform for incident data (moved from TASK-145.9 AC #4)
- [ ] #8 The dev incident commands (list, add-incident, load-incidents in modules/dev/incident.py) are deleted with their registrations; their pins and INVENTORY.md rows are updated
- [ ] #9 The projection adapter (append_row, update_status) lands in core before TASK-145.8's status cutover, inert until a writer registers
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-09 (human): the program breakdown and the revised recommendations of the second OQ assessment comment on TASK-145.7 (OQ1-OQ20), including the L5r rollback guard, the on-call capability path (25.6 -> 146.1, 146.3 in L9a), L9c and the IncidentBinding rename. Subtasks created 2026-11-09. Stack L program re-plan of 2026-11-09 against main 3075170b; cross-task order and rules in TASK-145.7's plan (sections 0 and 2) and doc-11 row 18. Supersedes the 2026-10-09 outline, whose "infrastructure.spreadsheets or the frozen module" dependency contradicts AC #6 (TASK-169 ruling: an incident-owned adapter over integrations/google_workspace). Two PRs:
- L4c projection adapter (~150 / 4, incident core; inert; early because TASK-145.8 L6b's status fan-out and 145.7 L9a's declare need it): core/api.py IncidentListProjection Protocol (append_row(incident), update_status(incident, status)), core/adapters/google_sheets.py over integrations/google_workspace (AC #6), fake + parity test, list_sheet_id from [incident_core] (AC #5: each writing subdomain states it as required when it registers its first writer, L6b and L9b). Legacy writers today: incident_folder.py:279 add_new_incident_to_list (append_values :304), :311 update_spreadsheet_incident_status. Row format copied from them (pinned by the declare pin's sheet assertions).
- L11 projection becomes write-only (~250 mostly deletions / ~8, response + legacy; waits L9b, L10b): /sre incident list active and stale read IncidentStore.list_open (AC #3); the duplicate-row check (modules/incident/core.py ~251, verify) removed; get_incidents_from_sheet (:411) and create_missing_incidents (:523) deleted with their caller and tests (AC #2); the dev incident commands (modules/dev/incident.py list, add-incident :104, load-incidents) deleted (AC #2: no code writes a legacy-shape item; dev list already breaks on end-state items after L9b: OQ17); 145.9's AC #4 import check verified here. After deploy: the job rerun (L12, human) recorded in the notes (AC #2).
Blast radius: L4c none (inert). L11: list active/stale output (pinned) and dev-only commands; one revert.
Assumptions: the legacy row format has no reader other than people (AC #1); verify rg for get_incidents_from_sheet callers at L11.

## Subtasks (created 2026-11-09)
L0 TASK-145.7.1; L1 TASK-145.7.2; L2a TASK-145.7.3; L2b TASK-145.7.4; L3 TASK-145.8.1; L4a TASK-145.7.5; L4b TASK-145.7.6; L4c TASK-145.12.1; L5 TASK-145.7.7; L5r TASK-145.8.2; L6a TASK-145.8.3; L6b TASK-145.8.4; L7a TASK-145.8.5; L7b TASK-145.8.6; L8 TASK-145.7.8; L9a TASK-145.7.9; L9b TASK-145.7.10; L9c TASK-145.7.11; L10a TASK-145.9.1; L10b TASK-145.9.2; L10c TASK-145.9.3; L10d TASK-145.9.4; L11 TASK-145.12.2; side: TASK-25.6 -> TASK-146.1 (before L9a); TASK-146.3 delivered by TASK-145.7.9; L12 (job rerun) is TASK-145.12.2's notes. Other slices are planned in full at pickup.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14 (TASK-145.5 split): references carry the vendor's own tenant id: the Slack team_id and the Google Workspace customer id from the platform settings added in TASK-145.5.3, never an invented label.

2026-10-15: the legacy backfill moved to the TASK-145.5.7 upgrade job (human); this task removes the sheet import, the last legacy writer, and reruns that job after deploy.

2026-10-20 (TASK-27.5 planning): AC3 rewritten. The whole-table read rule (decisions/cloud-portability.md contract 4) makes listings an index read (list_open) and removes the sheet duplicate-row check; only the rebuild uses read_all.

2026-10-28 (TASK-111.14): new incident list rows hold the channel as Slack's deep link (slack.com/app_redirect?channel=<id>&team=<team_id>), older rows hold gcdigital.slack.com/archives/<id>; modules/incident/incident_folder.channel_id_from_link reads both until the sheet import is removed here.

2026-11-04 (TASK-145.5.7 planning, human): the whole-table cap is the files key [incident_core] full_read_max_items, not an environment name (decisions/cloud-portability.md contract 4 amended); AC3 and step 3 reworded. The rerun of the TASK-145.5.7 job after this task merges is a dry run then apply per environment.

2026-11-05: no longer waits on TASK-121; it owns its sheet port and 121 deletes infrastructure/spreadsheets after it (TASK-169 ruling, 2026-11-05 (human), D5).

2026-11-06 (TASK-36.1.2 OQ1/OQ6, human-approved): legacy pin and cutover rules apply: decisions/migration.md recipe steps 2 and 4, decisions/transport-slack.md (legacy ids), decisions/testing.md (seams during the legacy migration); checklist in the implementation-planning skill (Legacy Surfaces). Rebuild/cutover task: pins pass with assertions unchanged; fixtures rewired to the target Protocol fakes and their seam-baseline entries removed; legacy_only_* tests for behaviour it ends deleted; modal-internal ids take the plugin prefix, ids on posted messages stay as legacy aliases; new tests in the strict zone (make check-test-seams, TASK-187).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-09T18:37:00Z

---

Stack L OQ assessment 2026-11-09 (OQ3): AC #6 is delivered by the L4c projection adapter, before this task's L11 cutover, because 145.8's status fan-out needs the writer. OQ17: the dev incident commands (modules/dev/incident.py list, add-incident, load-incidents) are deleted in L11 under AC #2; pins test_slack_command_registration_surface.py:88, :91, :207 and INVENTORY.md:121 updated there.

---
<!-- COMMENTS:END -->
