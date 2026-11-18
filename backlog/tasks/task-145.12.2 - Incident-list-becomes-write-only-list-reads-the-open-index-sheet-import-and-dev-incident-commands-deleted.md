---
id: TASK-145.12.2
title: >-
  Incident list becomes write-only: list reads the open index; sheet import and
  dev incident commands deleted
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-17T20:56:00Z'
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

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-16T15:51:00Z

---

2026-11-16 (human, TASK-145.8.4 OQ4): decisions/migration.md step 4 amended (rides with L6b): a cutover changes behaviour only as a named change of kind (a) legacy bug no pin asserts, (b) behaviour an accepted end-state ADR replaces, (c) expired deprecated form after a usage check, (d) retired surface; additions only by an explicit plan ruling. At planning, classify each behaviour change of this task by kind, pin it (test_legacy_only_* or edited pin citing the ruling) and list it in the PR body.

---

created: 2026-11-17T20:56:00Z

---

2026-11-17 (TASK-145.8.3 OQ8): the legacy sheet-status writer (incident_folder.update_spreadsheet_incident_status, return_channel_name, channel_slug) is deleted by TASK-145.8.3 with its last caller; the status cell moves through the list projection (change_status). Nothing of it is left for this task.

---
<!-- COMMENTS:END -->
