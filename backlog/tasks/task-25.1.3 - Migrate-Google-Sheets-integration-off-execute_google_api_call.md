---
id: TASK-25.1.3
title: Migrate Google Sheets integration off execute_google_api_call
status: To Do
assignee: []
created_date: '2026-07-31 18:32'
updated_date: '2026-09-01 15:35'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.2
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/sheets.py
parent_task_id: TASK-25.1
priority: high
ordinal: 114000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-25.1. Migrate integrations/google_workspace/sheets.py off google_service.py's execute_google_api_call dispatcher onto a factory-built, stub-typed Resource (SheetsResource from google-api-python-client-stubs, per decisions/sdk-typing.md item 3) + classify_google_error (extend with any Sheets-specific HttpError families, notably the existing non-critical get_sheet 'Unable to parse range' warning handling in google_service.py's handle_google_api_errors decorator - preserve that behavior exactly). Production consumers (grep-confirmed 2026-07-31): modules/incident/incident_folder.py, modules/aws/spending.py, modules/reports/google_groups.py (Sheets-related calls only in each file; their Drive/Directory-related calls belong to sibling slices).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/google_workspace/sheets.py no longer calls execute_google_api_call; routes through a factory-built, stub-typed Resource + classify_google_error, raising/classifying per the outbound-clients.md contract
- [ ] #2 The 3 identified consumer files behave identically for their Sheets-related calls (existing tests pass, behavior-neutral), including the get_sheet 'Unable to parse range' non-critical warning preserved
- [ ] #3 classify_google_error gains any Sheets-specific mapped families with unit coverage under tests/unit/integrations/google_workspace/
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: task-planner
created: 2026-09-01 15:34
---
TRACKING NOTE (2026-09-01, task-planner): TASK-25.1.1 introduces a shared integrations/google_workspace/client.py::execute_google_api_request(request) helper (try/except + classify_google_error + log + raise) as a deliberate, TEMPORARY deviation from outbound-clients.md's exact vendor-package export contract, tracked by TASK-25.1.6. When implementing this slice, if sheets.py's migrated call sites use execute_google_api_request (or you introduce an equivalent), update TASK-25.1.6's description/references with the exact files and call sites added here, so its eventual inline-vs-formalize decision is made against the full call-site inventory, not just TASK-25.1.1's.
---
<!-- COMMENTS:END -->
