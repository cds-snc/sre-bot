---
id: TASK-25.1.5
title: Migrate Google Drive integration off execute_google_api_call
status: To Do
assignee: []
created_date: '2026-07-31 18:33'
updated_date: '2026-09-01 15:35'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.4
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/google_drive.py
parent_task_id: TASK-25.1
priority: high
ordinal: 116000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 (largest, done last) of TASK-25.1. Migrate integrations/google_workspace/google_drive.py off google_service.py's execute_google_api_call dispatcher onto a factory-built, stub-typed Resource (DriveResource from google-api-python-client-stubs, per decisions/sdk-typing.md item 3) + classify_google_error (extend with any Drive-specific HttpError families beyond what prior slices established). Production consumers (grep-confirmed 2026-07-31, the largest surface - 8 files): modules/incident/incident_document.py, modules/incident/incident_helper.py, modules/incident/incident_folder.py, modules/incident/core.py, modules/incident/incident_roles.py, modules/role/role.py, jobs/scheduled_tasks.py, modules/reports/google_groups.py (Drive-related calls only in each file; their Docs/Sheets/Directory-related calls are covered by sibling slices). Done last so the factory/classify extraction pattern is already proven on 4 smaller surfaces first.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/google_workspace/google_drive.py no longer calls execute_google_api_call; routes through a factory-built, stub-typed Resource + classify_google_error, raising/classifying per the outbound-clients.md contract
- [ ] #2 All 8 identified consumer files behave identically for their Drive-related calls (existing tests pass, behavior-neutral)
- [ ] #3 classify_google_error gains any Drive-specific mapped families with unit coverage under tests/unit/integrations/google_workspace/; integrations/google_workspace/google_service.py's execute_google_api_call dispatcher has zero remaining callers repo-wide once this slice lands (verify via grep, feeding TASK-25.1's own coordinator AC#1)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: task-planner
created: 2026-09-01 15:35
---
TRACKING NOTE (2026-09-01, task-planner): TASK-25.1.1 introduces a shared integrations/google_workspace/client.py::execute_google_api_request(request) helper (try/except + classify_google_error + log + raise) as a deliberate, TEMPORARY deviation from outbound-clients.md's exact vendor-package export contract, tracked by TASK-25.1.6. When implementing this slice, if google_drive.py's migrated call sites use execute_google_api_request (or you introduce an equivalent), update TASK-25.1.6's description/references with the exact files and call sites added here, so its eventual inline-vs-formalize decision is made against the full call-site inventory, not just TASK-25.1.1's. This is the last TASK-25.1 child (25.1.6 depends on it), so its landing should trigger TASK-25.1.6's implementation.
---
<!-- COMMENTS:END -->
