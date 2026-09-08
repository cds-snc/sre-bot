---
id: TASK-25.1.6.8
title: Move live incident and jobs Drive call sites onto the incident Drive adapter
status: To Do
assignee: []
created_date: '2026-09-02 15:02'
updated_date: '2026-09-08 14:44'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.7
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/google_drive.py
  - app/modules/incident/incident_folder.py
parent_task_id: TASK-25.1.6
priority: medium
ordinal: 139000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move the live Drive consumers in modules/incident/{incident_document,incident_helper,incident_folder,core,incident_roles}.py, modules/role/role.py, and jobs/scheduled_tasks.py onto the incident Drive adapter established by TASK-25.1.6.7. Retire the temporary folder display shim or assign a separate product follow-up. The unused modules/reports/google_groups.py feature is excluded from this migration and is deleted by TASK-25.1.6.10; do not recreate or migrate its Drive calls.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The incident Drive adapter builds a stub-typed DriveResource via get_drive_service, calls files() methods directly, and performs its own try/except + classify_google_error.
- [ ] #2 The Drive q-DSL query builders, file_type-to-mimeType map and ValueError, copy-then-move composition, healthcheck, and appProperties metadata convention live in the adapter, not app/integrations.
- [ ] #3 All seven live incident, role, and jobs consumers call the adapter; none imports integrations.google_workspace.google_drive.
- [ ] #4 app/integrations/google_workspace/google_drive.py and its test file are deleted, with no remaining production references.
- [ ] #5 LEGACY_FOLDER_DISPLAY_LIMIT is removed in favour of a real Slack pagination/search solution, or a linked follow-up owns that product change.
- [ ] #6 Pagination established by TASK-25.1.5 is preserved and proven by a multi-page adapter test.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-02 17:16
---
PRE-REGISTERED BY TASK-25.1.6.1 PLANNING (2026-09-02, task-planner). Your AC#6 depends on TASK-25.1.6.1 characterization tests for modules/reports/google_groups.py. What lands:

FILE: app/tests/unit/modules/reports/test_google_groups_report.py (unit tree, per the AC correction on TASK-25.1.6.1 -- not app/tests/modules/).

WHAT COVERS YOUR TWO DRIVE SITES: TestGenerateGroupMembersReportBoundary pins google_drive.find_files_by_name("groups_report_<YYYY-MM-DD>", folder_id) under freeze_time, google_drive.create_file(filename, folder_id, "spreadsheet") when the lookup returns [], and create_file NOT being called plus files[0]["id"] being reused as the spreadsheet id when it returns a hit. Those assertions are yours to TRANSLATE onto the incident Drive adapter seam, not to delete.

TWO THINGS THE TESTS DELIBERATELY PIN THAT YOU MAY WANT TO CHANGE -- if you do, name it in your notes:
- The spreadsheet is created BEFORE the empty-groups check, so a run with zero groups still leaves an empty spreadsheet in Drive. TestGenerateGroupMembersReportBehaviour asserts that ordering explicitly.
- find_files_by_name raising propagates uncaught out of generate_group_members_report today, with respond() never called. TestGenerateGroupMembersReportFailureModes asserts that. Once the adapter classifies into OperationResult that exception stops crossing the boundary, so this test will need rewriting -- that is an intentional change, not a regression.

NOTE ON create_file: the file_type-to-mimeType map and its ValueError live in google_drive.create_file and your AC#2 moves them into the adapter. The reports call passes the literal "spreadsheet"; the characterization tests assert the string that is passed, not the mimeType, so the map move is invisible to them.
---

created: 2026-09-08 14:44
---
SCOPE UPDATE (2026-09-08): modules/reports/google_groups.py is not a live Drive consumer for this work. Delete the legacy report module under TASK-25.1.6.10 instead of moving its Drive calls into the incident adapter; this task covers only live incident and jobs Drive consumers.
---

created: 2026-09-08 14:44
---
SCOPE UPDATE (2026-09-08): acceptance criteria were refreshed to remove the unused modules/reports/google_groups.py consumer. Its deletion is owned by TASK-25.1.6.10; this task now covers seven live consumers only.
---
<!-- COMMENTS:END -->
