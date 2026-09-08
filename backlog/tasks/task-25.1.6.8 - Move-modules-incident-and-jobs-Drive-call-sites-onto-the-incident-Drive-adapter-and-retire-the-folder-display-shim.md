---
id: TASK-25.1.6.8
title: >-
  Retire google_drive.py: introduce a Drive infrastructure capability and
  incident/role feature adapters
status: To Do
assignee: []
created_date: '2026-09-02 15:02'
updated_date: '2026-09-08 18:58'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.7
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - app/integrations/google_workspace/google_drive.py
  - app/modules/incident/incident_folder.py
parent_task_id: TASK-25.1.6
priority: medium
ordinal: 139000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR TASK (retitled and rescoped 2026-09-08 during planning, human-directed — see TASK-25.1.6's 2026-09-08 pivot comment for full rationale). Originally scoped as a single "move seven consumers onto the incident Drive adapter" slice; research found that 2 of those 7 call sites (modules/role/role.py: create_folder + copy_file_to_folder x7) belong to the unrelated talent/hiring "role" workflow, not the incident feature, with no packages/role package existing. Rather than force an unrelated feature to import packages/incident's adapter, or build two duplicate Path-B adapters, Drive graduates directly to a Path A infrastructure capability (two independent feature consumers are already known upfront — decisions/layers.md's "promotion on second consumer" trigger, applied proactively).

THREE CHILDREN, in dependency order:
- TASK-25.1.6.8.1 — build app/infrastructure/drive/ (DriveProvider Protocol + GoogleDriveProvider + settings + factory), mirroring app/infrastructure/directory/'s shape. Touches no consumer file; does not delete google_drive.py.
- TASK-25.1.6.8.2 — build a packages/incident/<subdomain>/adapters/google_drive.py on top of DriveProvider; migrate core.py, incident_document.py, incident_folder.py, incident_roles.py, and jobs/scheduled_tasks.py's Drive healthcheck.
- TASK-25.1.6.8.3 — build a new packages/role/adapters/google_drive.py on top of DriveProvider; migrate modules/role/role.py.

NOT OWNED BY THIS COORDINATOR OR ITS CHILDREN: modules/reports/google_groups.py (deleted outright, not migrated) and the actual deletion of app/integrations/google_workspace/google_drive.py + its test file — both belong to TASK-25.1.6.10, since google_groups.py's two remaining calls (find_files_by_name, create_file) are the last production references to google_drive.py and TASK-25.1.6.10 is what removes them. This task's own AC#4 (below) reflects that boundary rather than requiring the file's deletion here.

The real Slack pagination/search fix for LEGACY_FOLDER_DISPLAY_LIMIT is out of scope of every child; it is tracked by TASK-81.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/infrastructure/drive/ exists (DriveProvider Protocol, GoogleDriveProvider, settings, factory) per TASK-25.1.6.8.1
- [ ] #2 packages/incident/<subdomain>/adapters/google_drive.py exists and core.py, incident_document.py, incident_folder.py, incident_roles.py, and jobs/scheduled_tasks.py call it; none imports integrations.google_workspace.google_drive (TASK-25.1.6.8.2)
- [ ] #3 packages/role/adapters/google_drive.py exists and modules/role/role.py calls it; it no longer imports integrations.google_workspace.google_drive (TASK-25.1.6.8.3)
- [ ] #4 app/integrations/google_workspace/google_drive.py is not yet deleted by this coordinator or its children — its last production references (modules/reports/google_groups.py) are removed by TASK-25.1.6.10, which owns the file's actual deletion
- [ ] #5 LEGACY_FOLDER_DISPLAY_LIMIT is untouched or removed only if TASK-81 has already landed; TASK-81 owns the real fix
- [ ] #6 Focused tests, ruff, mypy, and app/bin/check_sdk_typing.py pass for all three children
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

created: 2026-09-08 18:58
---
RETITLED AND RESCOPED 2026-09-08 (task-planner, human-directed). The prior 7-consumer, single-adapter framing (and its file_type-to-mimeType/ValueError AC clause, which only ever served modules/reports/google_groups.py's dead-not-migrated create_file call) is replaced wholesale by the 3-child coordinator structure above. See TASK-25.1.6's pivot comment for the architecture rationale, and TASK-25.1.6.10's updated AC for where google_drive.py's actual deletion now lives.
---
<!-- COMMENTS:END -->
