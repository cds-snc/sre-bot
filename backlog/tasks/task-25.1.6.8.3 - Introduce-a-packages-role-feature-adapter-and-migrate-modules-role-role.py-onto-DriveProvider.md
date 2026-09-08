---
id: TASK-25.1.6.8.3
title: >-
  Introduce a packages/role feature adapter and migrate modules/role/role.py
  onto DriveProvider
status: To Do
assignee: []
created_date: '2026-09-08 18:58'
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
  - decisions/migration.md
  - app/packages/incident/documents/adapters/google_docs.py
  - app/modules/role/role.py
parent_task_id: TASK-25.1.6.8
priority: medium
ordinal: 158000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
modules/role/role.py (the talent/hiring interview-panel workflow) calls google_drive.create_folder once and google_drive.copy_file_to_folder seven times (template-copying interview documents into a newly-created candidate folder). This is unrelated to the incident feature — it must not be routed through packages/incident's adapter.

No packages/role package exists today. This task creates one: a minimal new app/packages/role/ (empty __init__.py, no hookimpl — decisions/migration.md rule 5's lighter path, since role.py stays the registered/frozen legacy module and this is a host-surface-free relocation of Drive I/O, not a capability migration) holding adapters/google_drive.py, built on TASK-25.1.6.8.1's DriveProvider (via infrastructure.drive.factory.get_drive_provider(), never constructing GoogleDriveProvider directly).

ADAPTER SHAPE: mirrors packages/incident/documents/adapters/google_docs.py — domain-oriented function names (e.g. create_role_folder, copy_template_to_role_folder), each translating DriveProvider's OperationResult into whatever role.py's call sites need (today's create_folder/copy_file_to_folder return a dict / a bare id string respectively; preserve those return shapes so role.py's existing isinstance/None-checking logic needs minimal changes), with its own logging on failure.

DELEGATION: role.py passes delegated_user_email=BOT_EMAIL (google_settings.SRE_BOT_EMAIL) explicitly on every call today — preserve this exactly; do not rely on DriveProvider's default (undelegated) behaviour for this feature.

NOT IN SCOPE: modules/incident/*, jobs/scheduled_tasks.py, modules/reports/google_groups.py (TASK-25.1.6.8.2 / TASK-25.1.6.10), and deleting app/integrations/google_workspace/google_drive.py itself (TASK-25.1.6.10 — google_groups.py keeps calling it until then).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A new packages/role/ package exists (empty __init__.py, no hookimpl/entry-point) with adapters/google_drive.py built on infrastructure.drive.factory.get_drive_provider(), never constructing GoogleDriveProvider directly
- [ ] #2 modules/role/role.py calls the adapter for both its folder-creation and template-copy operations, passing delegated_user_email=BOT_EMAIL through unchanged; it no longer imports integrations.google_workspace.google_drive
- [ ] #3 Existing test_role.py Drive-related coverage is preserved at the new boundary
- [ ] #4 Focused tests, ruff, mypy, and app/bin/check_sdk_typing.py pass
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-08 20:12
---
2026-09-08 portability confirmation: this task can proceed unchanged against the adjusted DriveProvider. create_folder and copy_file_to_folder are shared file/folder capabilities; the role adapter preserves BOT_EMAIL by passing delegated_user_email through the Google implementation boundary, while modules/role/role.py calls only the role adapter. No metadata or other Google-only behavior is involved. Keep the adapter domain-oriented and preserve the existing return shapes and failure logging.
---
<!-- COMMENTS:END -->
