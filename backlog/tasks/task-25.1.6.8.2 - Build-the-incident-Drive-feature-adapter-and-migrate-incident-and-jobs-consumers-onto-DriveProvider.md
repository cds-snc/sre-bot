---
id: TASK-25.1.6.8.2
title: >-
  Build the incident Drive feature adapter and migrate incident and jobs
  consumers onto DriveProvider
status: To Do
assignee: []
created_date: '2026-09-08 18:57'
updated_date: '2026-09-08 20:12'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.8.1
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/feature-packages.md
  - app/packages/incident/documents/adapters/google_docs.py
  - app/modules/incident/core.py
  - app/modules/incident/incident_document.py
  - app/modules/incident/incident_folder.py
  - app/modules/incident/incident_roles.py
  - app/jobs/scheduled_tasks.py
parent_task_id: TASK-25.1.6.8
priority: medium
ordinal: 156000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Build a thin incident-owned Drive adapter over TASK-25.1.6.8.1's DriveProvider and repoint the five in-scope incident/jobs consumers onto it: app/modules/incident/core.py (list_files_in_folder), incident_document.py (create_file_from_template), incident_folder.py (list_folders_in_folder x2, delete_metadata, add_metadata, list_metadata x2), incident_roles.py (add_metadata x2, find_files_by_name), and app/jobs/scheduled_tasks.py (the google_drive.healthcheck entry in integration_healthchecks()).

PACKAGE HOME: a new subdomain under the existing packages/incident/ umbrella (empty __init__.py, no hookimpl — mirrors packages/incident/documents/ from TASK-25.1.6.7 and packages/incident/scheduling/ from TASK-25.1.6.2). Proposed name "folders" (packages/incident/folders/adapters/google_drive.py) matching incident_folder.py's own vocabulary — confirm or rename during this task's own planning pass; not locked by this coordinator-level scaffolding.

ADAPTER SHAPE: domain-oriented function names (not SDK passthroughs), each calling into DriveProvider (via infrastructure/drive/factory.py::get_drive_provider(), never constructing GoogleDriveProvider directly — decisions/dependency-injection.md), translating OperationResult into whatever each caller needs (bool/dict/None on failure, matching today's per-call-site behavior) and logging its own warning event on failure — mirrors packages/incident/documents/adapters/google_docs.py's replace_placeholders/fetch_document_content/apply_document_edits shape exactly (no execute_google_api_request, no shared generic passthrough).

INCIDENT-SPECIFIC HEALTH CHECK: today's app/integrations/google_workspace/google_drive.py::healthcheck() checks the incident template file's metadata specifically (INCIDENT_TEMPLATE = get_google_resources_config().incident_template_id) — this is incident-domain knowledge, not generic Drive connectivity, so it does NOT become DriveProvider.health_check() (TASK-25.1.6.8.1's Protocol method is a generic, cheap liveness check only). Instead, this adapter exposes its own health-check function built on DriveProvider.get_metadata(INCIDENT_TEMPLATE), and jobs/scheduled_tasks.py calls that instead of google_drive.healthcheck.

LEGACY_FOLDER_DISPLAY_LIMIT: retire the shim only if the linked Slack pagination/search follow-up task has landed; otherwise leave it in place unchanged and keep pointing at that follow-up (see TASK references) — do not attempt the real Slack UI fix as part of this migration.

NOT IN SCOPE: modules/role/role.py (TASK-25.1.6.8.3, different feature, different package), modules/reports/google_groups.py (deleted outright by TASK-25.1.6.10, not migrated), and deleting app/integrations/google_workspace/google_drive.py itself (also TASK-25.1.6.10 — google_groups.py keeps calling it until then).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A new packages/incident/<subdomain>/adapters/google_drive.py (no hookimpl, empty subdomain __init__.py) exposes domain-oriented functions built on infrastructure.drive.factory.get_drive_provider(), never constructing GoogleDriveProvider directly
- [ ] #2 core.py, incident_document.py, incident_folder.py, incident_roles.py, and jobs/scheduled_tasks.py call the adapter; none imports integrations.google_workspace.google_drive
- [ ] #3 jobs/scheduled_tasks.py's integration_healthchecks() calls a new incident-owned health-check function built on DriveProvider.get_metadata(INCIDENT_TEMPLATE), not a generic DriveProvider.health_check()
- [ ] #4 LEGACY_FOLDER_DISPLAY_LIMIT is left unchanged with its follow-up (TASK-81) reference intact; this task does not implement the real Slack pagination/search fix
- [ ] #5 Existing incident/jobs Drive test coverage (test_incident_document.py, test_incident_folder.py, test_incident_roles.py, test_recreate_missing_resources.py, test_scheduled_tasks_integration.py) is preserved at the new boundary
- [ ] #6 Focused tests, ruff, mypy, and app/bin/check_sdk_typing.py pass
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-08 18:57
---
TASK-81 created (2026-09-08) as the linked Slack pagination/search follow-up for LEGACY_FOLDER_DISPLAY_LIMIT. AC#4 updated to reference it by ID instead of describing it generically.
---

created: 2026-09-08 20:12
---
2026-09-08 portability adjustment: this task remains implementable, but its adapter boundary must distinguish common Drive operations from incident-specific Google metadata. Migrate core.py, incident_document.py, incident_folder.py, incident_roles.py, and scheduled_tasks.py so consumers call the incident-owned adapter only. The adapter uses DriveProvider for folder/file listing, template creation, and name lookup. It owns appProperties reads/writes and the incident-template health check as Google-specific feature behavior, temporarily delegating to the legacy google_workspace.google_drive metadata helpers (or an equivalent adapter-local classified client call) until TASK-25.1.6.10 removes that integration. Do not restore get_metadata/set_metadata_property/delete_metadata_property to the vendor-neutral DriveProvider; revise AC#3's wording from DriveProvider.get_metadata to the incident adapter's Google metadata helper. This is a full consumer migration: legacy modules/jobs no longer import the Google integration directly; only the feature adapter may retain the temporary vendor dependency.
---
<!-- COMMENTS:END -->
