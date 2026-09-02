---
id: TASK-25.1.6.10
title: >-
  Move the Sheets call sites onto adapters and carry across the parse-range
  business rule
status: To Do
assignee: []
created_date: '2026-09-02 15:03'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.7
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/sheets.py
  - app/modules/incident/incident_folder.py
  - app/modules/aws/spending.py
  - app/modules/reports/google_groups.py
parent_task_id: TASK-25.1.6
priority: medium
ordinal: 141000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Sheets slice. Three consumers across two feature areas, so it may warrant splitting at planning time; follows TASK-25.1.6.7's boundary-placement decision for the incident half.

CONSUMERS (recorded by TASK-25.1.3 at implementation time): modules/incident/incident_folder.py (append_values, get_values, batch_update_values, get_sheet), modules/reports/google_groups.py (get_sheet), modules/aws/spending.py (values calls only). integrations/google_workspace/sheets.py has five execute_google_api_request call sites, all of them SDK mirrors adding nothing over the SDK - get_values, get_sheet, batch_update, batch_update_values, append_values.

THE ONE PIECE OF REAL BUSINESS LOGIC, AND WHERE IT BELONGS: TASK-25.1.3 relocated a non-critical 'Unable to parse range' swallow out of google_service.py's handle_google_api_errors decorator into modules/incident/incident_folder.py::get_incidents_from_sheet (try/except HttpError -> warn + return []; any other HttpError re-raised). Its own notes call this the concrete precedent for what inline classification should look like: it is CALLER-SPECIFIC and must NOT move back into a shared layer. Carry it across to the incident Sheets adapter method that serves get_incidents_from_sheet, or keep it at the caller - but keep it caller-specific either way, and do not generalise it into the adapter's shared error handling.

modules/reports/google_groups.py's get_sheet call is wrapped in a blanket 'except Exception: sheet = None'. That is exactly the imprecise handling classify_google_error is meant to replace; replacing it is a real behaviour change and is guarded only by TASK-25.1.6.1's characterization tests, which are a hard prerequisite for this file. Same for modules/aws/spending.py, which has no coverage of its Sheets sites at all.

SCOPE: each consuming area's adapter builds a stub-typed SheetsResource via get_sheets_service, calls spreadsheets() methods directly with its own try/except + classify_google_error, and returns typed results. integrations/google_workspace/sheets.py is deleted.

NOTE: app/tests/integrations/google_workspace/test_sheets.py:250 contains a hasattr assertion referencing execute_google_api_call; it is one of only two remaining repo-wide matches for that name and dies with this file.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every Sheets call site builds a stub-typed SheetsResource via get_sheets_service and performs its own try/except + classify_google_error; no consumer imports integrations.google_workspace.sheets
- [ ] #2 The 'Unable to parse range' non-critical swallow remains caller-specific to the incidents-sheet read - it is preserved in behaviour and is not generalised into shared adapter error handling; a test covers both the swallowed case and the re-raised other-HttpError case
- [ ] #3 modules/reports/google_groups.py's blanket 'except Exception: sheet = None' around get_sheet is replaced by explicit classification-based handling, with TASK-25.1.6.1's characterization tests passing or each intentional change named in the notes
- [ ] #4 modules/aws/spending.py's Sheets call sites are migrated with TASK-25.1.6.1's characterization tests passing
- [ ] #5 app/integrations/google_workspace/sheets.py is deleted with its test file, grep-verified zero references repo-wide outside backlog/ and tmp/
- [ ] #6 After this task, grep for execute_google_api_call repo-wide matches only bin/check_sdk_typing.py's own detection regex
<!-- AC:END -->
