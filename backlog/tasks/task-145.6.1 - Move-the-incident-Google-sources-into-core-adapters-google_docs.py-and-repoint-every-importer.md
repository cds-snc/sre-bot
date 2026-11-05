---
id: TASK-145.6.1
title: >-
  Move the incident Google sources into core/adapters/google_docs.py and repoint
  every importer
status: To Do
assignee: []
created_date: '2026-11-05T00:44:00Z'
updated_date: '2026-11-05T00:44:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.5.7.3
parent_task_id: TASK-145.6
priority: medium
ordinal: 481000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 12a of Stack K (TASK-145.6 plan, approved 2026-11-05). Mechanical only: no new type, no behaviour change. The bodies of features/incident/documents/ (adapters/google_docs.py, utils.py), features/incident/drive/adapters/google_drive.py (folders, appProperties metadata, healthcheck) and scribe/adapters/google_docs.py (the section writer, one module) move verbatim into features/incident/core/adapters/google_docs.py; every production and test importer and mock.patch string is repointed (migration.md rule 5), including modules/incident/* and jobs/scheduled_tasks.py; the three sources are deleted; the umbrella layers contract drops documents and drive; the import-linter ignores for these modules are renamed to the core module without growing. Built above TASK-145.5.7.3 (#1822).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/incident/documents/, features/incident/drive/ and scribe/adapters/google_docs.py no longer exist; their code lives verbatim in features/incident/core/adapters/google_docs.py
- [ ] #2 rg finds no import or patch string naming features.incident.documents, features.incident.drive or features.incident.scribe.adapters.google_docs anywhere in app/
- [ ] #3 The moved tests pass with only their import paths and patch strings changed; the legacy_surface, scribe and comms suites pass unchanged
- [ ] #4 The import-linter ignore entries for the moved modules name the core module and their count does not grow; the umbrella layers contract lists no documents or drive
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports, make check-import-contracts, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Derived from the TASK-145.6 plan approved 2026-11-05 (steps 1-4); call sites there. Branch stack-k/task-145.6.1-google-docs-move above #1822.
1. Tests first: move tests/unit/features/incident/documents/test_incident_documents_adapter.py, test_incident_documents_boundaries.py, drive/adapters/test_incident_drive_adapter.py and scribe/test_incident_scribe_draft_adapter.py to tests/unit/features/incident/core/test_incident_core_google_docs_{placeholders,boundaries,drive,sections}.py with only import paths and patch strings pointing at features.incident.core.adapters.google_docs; update the patch strings in scribe/test_incident_scribe_providers_document_store.py, test_incident_scribe_conversation_draft.py, tests/unit/modules/incident/test_incident_timeline_update.py, tests/unit/server/test_server_app_import_google_settings_lazy.py. They fail (module missing).
2. Create features/incident/core/adapters/google_docs.py: sections in order documents utils, documents adapter, drive adapter (folders, metadata, healthcheck), section writer, bodies verbatim; merge the import blocks; resolve any private-name collision by keeping the first and renaming the later one with a module prefix (recorded in notes).
3. Repoint production importers: scribe/providers.py:10-11; jobs/scheduled_tasks.py:12; modules/incident information_update.py:8, incident_conversation.py:12, incident_status.py:5, incident_roles.py:8, core.py:11, incident_folder.py:19, incident_helper.py:10, incident_document.py:11.
4. Delete features/incident/documents/, features/incident/drive/, scribe/adapters/google_docs.py and their empty test packages; pyproject.toml: rename ignores :303-306 to features.incident.core.adapters.google_docs (dedupe, never more lines), drop documents and drive from the umbrella layers contract.
5. Gates: ruff and the moved tests during the move; at the end mypy, then pytest, once each; lint-imports, make check-import-contracts, make check-settings-key-ownership.
AC map: #1 steps 2,4; #2 step 3 plus rg; #3 step 1; #4 step 4; #5 step 5.
Blast radius: import errors only, caught at import by every suite; one revert. No terraform, IAM, SSM or env change.
<!-- SECTION:PLAN:END -->
