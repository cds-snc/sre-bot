---
id: TASK-25.1.5.1
title: >-
  Repoint incident_draft's Drive calls onto get_drive_service with an inline
  adapter boundary
status: To Do
assignee: []
created_date: '2026-09-02 13:26'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.5
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - app/packages/incident_draft/adapters/google_docs.py
parent_task_id: TASK-25.1.5
priority: high
ordinal: 131000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split out of TASK-25.1.5 on 2026-09-02 because bundling it tripped the single-PR size gate. TASK-25.1.5 migrates the google_drive.py vendor module onto the stub-typed DriveResource; this slice moves the ONE real adapter among Drive's nine production consumers onto the vendor package's factory + its own inline try/except, per decisions/outbound-clients.md ("the adapter is the boundary", one adaptation tier).

app/packages/incident_draft/adapters/google_docs.py is the only app/packages/<feature>/adapters/ file that calls Drive (grep-confirmed 2026-09-02). It has two Drive call sites, both against functions that are pure SDK mirrors adding no domain value:
- :272 _copy_source_document -> google_drive.create_file_from_template(draft_title, folder, source_document_id, fields="id")
- :1245 -> google_drive.get_file_by_id(document_id, fields="id, name, parents")
It also calls google_drive.find_files_by_name, which builds a Drive q-DSL query and is genuine domain logic - that call stays on the vendor module.

Scope:
1. Repoint the two call sites onto integrations.google_workspace.client.get_drive_service(scopes=..., delegated_user_email=...) with the adapter's own try/except + classify_google_error, dropping their dependency on execute_google_api_request. This is the first Google call site in the repo to satisfy decisions/outbound-clients.md's adapter contract properly, and directly discharges part of TASK-25.1.6's AC#2.
2. Delete integrations/google_workspace/google_drive.py::get_file_by_id, which has zero remaining callers once step 1 lands (grep-confirmed: the adapter is its only consumer).
3. Leave create_file_from_template in place: modules/incident/incident_document.py:29 still calls it and is legacy app/modules/* with no adapter tier. Its retirement belongs to TASK-25.1.6's adapter work, not here.

SIZE WARNING for whoever plans this: app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py is 1704 lines with 135 mock_drive references, all patching packages.incident_draft.adapters.google_docs.google_drive as one module-level mock. Step 1 splits that boundary in two (a mocked DriveResource chain for the two repointed calls, the existing module mock for find_files_by_name) and invalidates shape assertions such as mock_drive.create_file.assert_not_called(). Expect the test rework, not the production change, to dominate this PR - plan a single shared DriveResource fake helper rather than reinventing the chain per test.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/incident_draft/adapters/google_docs.py builds its Drive calls from integrations.google_workspace.client.get_drive_service and wraps them in its own try/except + classify_google_error; neither Drive call site depends on execute_google_api_request or on a google_drive passthrough
- [ ] #2 integrations/google_workspace/google_drive.py::get_file_by_id is deleted, grep-verified zero callers repo-wide
- [ ] #3 The adapter still calls google_drive.find_files_by_name (genuine q-DSL domain logic) and create_file_from_template is left in place for its remaining legacy modules/ caller
- [ ] #4 tests/unit/packages/incident_draft/test_incident_draft_adapter.py is reworked onto the split mock boundary with a single shared DriveResource fake helper; every existing behavioral assertion is preserved or has a documented equivalent, and error-classification coverage is added for the two repointed call sites
- [ ] #5 TASK-25.1.6's call-site inventory is updated to record that these two sites are discharged (AC#2 bucket) and to remove them from its outstanding scope
<!-- AC:END -->
