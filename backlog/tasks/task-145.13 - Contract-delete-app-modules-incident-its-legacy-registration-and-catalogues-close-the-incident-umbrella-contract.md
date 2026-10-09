---
id: TASK-145.13
title: >-
  Contract: delete app/modules/incident, its legacy registration and catalogues;
  close the incident umbrella contract
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 18:23'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.11
  - TASK-145.12
  - TASK-118
parent_task_id: TASK-145
priority: medium
type: task
ordinal: 363000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer E2 of TASK-145. After the earlier layers every incident surface is rebuilt and cut over.

THIS SLICE
- Delete app/modules/incident/ and its entry in the legacy handler registration; delete the incident python-i18n catalogues under app/locales/ once the per-package catalogues carry every key (TASK-118 translator contract, parity gate green for EN and FR).
- Remove every freeze-baseline entry naming app/modules/incident; no baseline grows.
- app/tests/integration/legacy_surface/INVENTORY.md: every incident row points at its response, comms or postmortem handler and its pinning test; surfaces found outside the original inventory are listed with their disposition.
- modules/dev/incident.py and the /sre incident dispatcher in modules/sre are repointed or deleted.
- decisions/incident-management.md Migration: remove the closed tolerances and add a dated Changes line; decisions/migration.md and feature-packages.md Context lines naming modules/incident are updated.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/modules/incident/ does not exist; no module imports it; the legacy registration list has no incident entry
- [ ] #2 No freeze baseline names app/modules/incident; the import-linter ignore list has not grown
- [ ] #3 The legacy_surface inventory maps every incident surface to its new handler and pinning test
- [ ] #4 decisions/incident-management.md Migration lists no closed tolerance and carries a dated Changes line
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Outline plan grounded at main d2d973ae (2026-10-09); re-ground at pickup (after TASK-145.11, TASK-145.12 and TASK-118). Standalone PR.

## Discovered state
- app/modules/incident/ 17 files (incident_helper 720, core 617, incident_folder 522, incident 481, incident_conversation 460, schedule_retro 389, information_update 330, incident_document 304, db_operations 233, information_display 183, incident_roles 145, incident_alert 105, incident_status 81, notify_stale_incident_channels 50, on_call 41, utils 25). Outside importers: modules/sre/platforms/slack.py:16 (incident_helper), modules/dev/incident.py:5 (db_operations, incident_conversation, incident_folder), jobs/scheduled_tasks.py:15-16, tests/integration/legacy_surface/test_incident_updates_command_surface.py:25, tests/unit/modules/dev/test_dev_incident_handler.py, tests/unit/modules/incident/*. Catalogues app/locales/incident.{en-US,fr-FR}.yml. Legacy tests: 17 files under tests/modules/incident/ and 2 under tests/unit/modules/incident/.

## Steps
1. Delete app/modules/incident/ and its entry in the legacy handler registration; delete tests/modules/incident/ and tests/unit/modules/incident/ (their behaviour is covered by the response, comms and postmortem suites and the pinning tests); modules/dev/incident.py rewritten over core.api or deleted with its test; the /sre incident legacy route in modules/sre removed.
2. Delete app/locales/incident.*.yml once every key the three subdomains use lives in their catalogues and the parity gate is green (TASK-118).
3. Remove every freeze-baseline entry naming app/modules/incident; no baseline grows.
4. INVENTORY.md: every incident row points at its subdomain handler and pinning test; the extra surfaces (canvas, source-alert bookmark, floppy-disk handlers, recreate, the retired updates pointer) listed with their disposition.
5. decisions/incident-management.md: remove the closed tolerances, dated Changes line; decisions/migration.md and feature-packages.md Context lines naming modules/incident updated.

## AC traceability
AC1: step 1 -> `ls app/modules/incident` fails; `rg 'modules\.incident' app` empty. AC2: step 3 -> baseline diff shrink-only. AC3: step 4 -> review. AC4: step 5 -> review. AC5: gates.

## Test matrix
Boot: lifespan test loads every plugin; the legacy registration list has no incident entry; the full suite passes without the legacy tests.

## Assumptions and doubts
- modules/dev commands (load-incidents, add-incident) may still be wanted in dev; decide delete or rewrite at pickup.

## Size
Deletions mostly; about 100 lines of edits.

## Blast radius and rollback
Deleting the legacy module is final for the surfaces already cut over; a revert restores dead code only.
<!-- SECTION:PLAN:END -->
