---
id: TASK-25.1.6.8
title: >-
  Move modules incident and jobs Drive call sites onto the incident Drive
  adapter and retire the folder display shim
status: To Do
assignee: []
created_date: '2026-09-02 15:02'
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
Largest of the legacy-incident adapter slices. Follows the boundary-placement decision made in TASK-25.1.6.7 - do not re-decide it here.

CONSUMERS (grep-confirmed 2026-09-02, eight legacy files; the ninth, packages/incident_draft/adapters/google_docs.py, is handled by TASK-25.1.5.1 and TASK-25.1.6.6): modules/incident/incident_document.py, incident_helper.py, incident_folder.py, core.py, incident_roles.py, modules/role/role.py, modules/reports/google_groups.py, jobs/scheduled_tasks.py.

WHAT SURVIVES AND WHAT MOVES: TASK-25.1.5 deliberately kept google_drive.py for "what it genuinely adds over the SDK" - the Drive q-DSL query builders, the file_type-to-mimeType map and its ValueError, the copy-then-move composition, healthcheck, and the appProperties metadata convention. That is real domain logic, and decisions/outbound-clients.md forbids it in a vendor package. It moves INTO the adapter, it does not stay in integrations/. The pure SDK mirrors (add_metadata, delete_metadata, list_metadata, create_folder, create_file, create_file_from_template) become direct files() calls inside the adapter.

RETIRE THE SHIM: TASK-25.1.5 added modules/incident/incident_folder.py::LEGACY_FOLDER_DISPLAY_LIMIT = 25 as an explicitly temporary display cap, because fixing Drive pagination made folder listings unbounded while folder_item emits three Slack blocks per folder against a 100-block modal limit, and list_incident_folders() feeds four static_select option lists against a 100-option limit. It was registered on TASK-25.1.6 for retirement. The correct answer is pagination or search in the Slack UI - a product change. Either implement it here or, if it is genuinely a separate product decision, file it as its own task and link it, but do not silently leave the cap in place unowned.

ALSO IN SCOPE: modules/reports/google_groups.py's two Drive call sites (find_files_by_name, create_file). It has no test file today - TASK-25.1.6.1's characterization tests are the prerequisite guard.

SIZE: this touches eight consumer files plus the adapter and is the most likely of the TASK-25.1.6 children to need its own decomposition. Run it through the implementation-planning size gate before writing code; a reasonable split is incident-folder/metadata first, then document/roles/templating, then jobs and reports.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The incident Drive adapter (per TASK-25.1.6.7's placement decision) builds a stub-typed DriveResource via get_drive_service, calls files() methods directly, and performs its own try/except + classify_google_error at every call site
- [ ] #2 The Drive q-DSL query builders, the file_type-to-mimeType map and its ValueError, the copy-then-move composition, healthcheck and the appProperties metadata convention live in the adapter, not in app/integrations/
- [ ] #3 All eight legacy consumers call the adapter; none imports integrations.google_workspace.google_drive
- [ ] #4 app/integrations/google_workspace/google_drive.py is deleted with its test file, grep-verified zero references repo-wide outside backlog/ and tmp/
- [ ] #5 LEGACY_FOLDER_DISPLAY_LIMIT is either removed in favour of a real Slack pagination/search solution, or a linked follow-up task owns that product change and the constant carries a reference to it - it is not left unowned
- [ ] #6 modules/reports/google_groups.py's Drive call sites are migrated and TASK-25.1.6.1's characterization tests for that file pass, or each intentional change is named in the notes
- [ ] #7 Pagination behaviour established by TASK-25.1.5 (list_next drained to exhaustion, nextPageToken in the projection) is preserved through the move, proven by a multi-page test at the adapter boundary
<!-- AC:END -->
