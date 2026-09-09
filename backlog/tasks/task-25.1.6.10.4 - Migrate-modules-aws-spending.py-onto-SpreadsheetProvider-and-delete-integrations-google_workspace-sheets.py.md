---
id: TASK-25.1.6.10.4
title: >-
  Migrate modules/aws/spending.py onto SpreadsheetProvider and delete
  integrations/google_workspace/sheets.py
status: To Do
assignee: []
created_date: '2026-09-09 15:04'
updated_date: '2026-09-09 15:28'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.1.6.10.1
  - TASK-25.1.6.10.2
  - TASK-25.1.6.10.3
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/migration.md
  - app/modules/aws/spending.py
  - app/integrations/google_workspace/sheets.py
parent_task_id: TASK-25.1.6.10
priority: medium
ordinal: 162000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move the last Sheets consumer onto the shared capability and delete the vendor mirror module. This is the slice that takes app/integrations/google_workspace/sheets.py's production reference count to zero.

CALL SITE (grep-verified 2026-09-09): exactly one - modules/aws/spending.py:190 sheets.batch_update_values(spreadsheetId=..., cell_range='Sheet1', values=values, valueInputOption='USER_ENTERED') inside update_spending_data. It becomes get_spreadsheet_provider().update_values(spreadsheet_id, 'Sheet1', values).

CONSUMER SHAPE (decided 2026-09-09, human-directed): direct provider consumption from the legacy module, no feature adapter and no new feature package. One write call with no vendor-specific concepts does not justify a package home, and the Directory migration (TASK-25.1.6.4/.5) set this precedent for legacy modules.

FAILURE SEMANTICS - AN INTENTIONAL CHANGE TO NAME IN THE PR. Today a Sheets HttpError propagates out of update_spending_data uncaught (there is no try/except) and out of modules/aws/aws.py:121 and execute_spending_data_update_job. After migration the provider returns a classified OperationResult instead. Decide and record explicitly whether a failed write logs and returns or raises; the scheduled-job caller is the one whose behavior changes, so state which it is and cover it with a test rather than letting the choice fall out of the diff.

FOLDED-IN DEFECT (registered on TASK-25.1.6.10 by TASK-25.1.6.1 planning, 2026-09-02, and owned by this call site): update_spending_data declares spreadsheet_id=SPENDING_SHEET_ID as a DEFAULT ARGUMENT, evaluated at import time. The sheet id is frozen at process start, unaffected by later config resolution, and unpatchable via the module attribute - which is why every existing test must pass spreadsheet_id explicitly. execute_spending_data_update_job calls update_spending_data(spending_data) with no id, so production always uses that frozen value. Fix it while migrating the call site: resolve the id inside the function (get_google_resources_config().spending_sheet_id) rather than carrying the import-time binding across the seam. The module-level SPENDING_SHEET_ID constant and its _get_spending_sheet_id() helper go with it if nothing else uses them.

DELETION (the point of this slice): app/integrations/google_workspace/sheets.py and app/tests/integrations/google_workspace/test_sheets.py are deleted. Verify zero production references first - by this point modules/reports is gone (.10.1) and incident_folder.py is migrated (.10.3), so spending.py is the last one. This also removes 5 of the remaining execute_google_api_request call sites, shrinking TASK-25.1.6.11's surface.

NOT IN SCOPE: any other AWS/cost-explorer behavior in spending.py, the currency rates table, integrations/google_workspace/google_drive.py (TASK-25.1.6.10.5), and the deletion of execute_google_api_request itself (TASK-25.1.6.11).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/spending.py's single Sheets call site uses infrastructure.spreadsheets.get_spreadsheet_provider().update_values and the module no longer imports integrations.google_workspace.sheets; no feature adapter or new package is created
- [ ] #2 update_spending_data resolves the spreadsheet id inside the function instead of binding it as an import-time default argument; the existing skip-when-id-falsy branch still works and a test proves the id is no longer frozen at import
- [ ] #3 The exact values matrix crossing the boundary (header row followed by DataFrame rows, and the header-only empty-DataFrame case) is unchanged, proven by the existing assertions in app/tests/unit/modules/aws/test_spending_handler.py repointed to the provider seam
- [ ] #4 app/integrations/google_workspace/sheets.py and app/tests/integrations/google_workspace/test_sheets.py are deleted, with zero remaining production references to integrations.google_workspace.sheets repo-wide
- [ ] #5 Full test suite, ruff, mypy, and app/bin/check_sdk_typing.py pass
- [ ] #6 A classified write failure is logged with its status and error_code and does NOT propagate: update_spending_data returns without raising and execute_spending_data_update_job logs a failed run rather than crashing, with both covered by tests
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-09 15:28
---
FAILURE SEMANTICS DECIDED 2026-09-09 (human-directed), replacing the 'decide during implementation' AC.

DO NOT PRESERVE TODAY'S BEHAVIOR. Right now a Sheets HttpError propagates uncaught out of update_spending_data, out of modules/aws/aws.py:121 and out of execute_spending_data_update_job. That is drift from decisions/outbound-clients.md, not a contract worth carrying across the seam - the current code predates the architecture and is to be treated as outdated.

TARGET: the provider returns a classified OperationResult; update_spending_data logs the failure with status and error_code and returns; execute_spending_data_update_job logs a failed run. No exception crosses the boundary. This is safe here in a way it would not be for a read: nothing infers state from the absence of a write, unlike TASK-25.1.6.10.3's get_incidents_from_sheet, where an empty result would cause a duplicate row and therefore still raises.

THE RESULT HANDLING IN THE LEGACY MODULE IS AN EXPLICIT TEMPORARY SHIM. modules/aws/spending.py stays a frozen legacy module; the OperationResult check and its logging live there only until the AWS spending concern is rearchitected into a feature package, at which point a service owns the result and decides the user-facing outcome. Say so in a one-line comment at the call site so the shim is not mistaken for a permanent pattern, and do not build a result-translation helper for one call site.
---
<!-- COMMENTS:END -->
