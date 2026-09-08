---
id: TASK-25.1.6.10
title: >-
  Migrate live Sheets consumers and delete the legacy Google Groups report
  module
status: To Do
assignee: []
created_date: '2026-09-02 15:03'
updated_date: '2026-09-08 14:44'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.9
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
Migrate the live Sheets consumers in modules/incident/incident_folder.py and modules/aws/spending.py onto stub-typed SheetsResource calls with adapter-owned try/except + classify_google_error, preserving the incident parse-range behavior and removing the hand-rolled time.sleep rate limiter after SDK-native retries are configured. The unused legacy modules/reports/google_groups.py feature is not migrated: delete that module and its dedicated tests as part of this slice. Do not create a replacement reporting feature here; a future report capability requires a new feature task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Live incident-folder and AWS-spending Sheets calls use get_sheets_service and adapter-owned classification; no consumer imports integrations.google_workspace.sheets.
- [ ] #2 The incident parse-range behavior remains caller-specific and covered for both the swallowed expected error and propagated other HttpError.
- [ ] #3 The legacy modules/reports/google_groups.py module and its tests are deleted; no report behavior is migrated or recreated.
- [ ] #4 integrations/google_workspace/sheets.py and its tests are deleted, with no remaining production imports.
- [ ] #5 The report module time.sleep loop is removed with the module; live Sheets callers use SDK-native retry configuration.
- [ ] #6 Focused tests, ruff, mypy, and the SDK typing guard pass.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-02 17:17
---
PRE-REGISTERED BY TASK-25.1.6.1 PLANNING (2026-09-02, task-planner). Three items land in your scope.

1. CORRECTION TO YOUR PREMISE FOR modules/aws/spending.py. Your description says it "has no coverage of its Sheets sites at all". It has exactly ONE Sheets call site (sheets.batch_update_values:190 in update_spending_data) and app/tests/unit/modules/aws/test_spending_handler.py:102-133 already asserts spreadsheetId, cell_range, valueInputOption and the skip-when-id-falsy branch. TASK-25.1.3 notes looked at app/tests/modules/aws/, which does not exist. TASK-25.1.6.1 extends that existing file rather than creating a new one; it adds the exact values matrix (header row plus DataFrame rows), the empty-DataFrame case, spreadsheet_id="" skipping the call, and a raising Sheets call propagating out of update_spending_data (there is no try/except today). Your AC#4 should be read against that file, in place.

2. WHAT GUARDS modules/reports/google_groups.py Sheets sites. New file app/tests/unit/modules/reports/test_google_groups_report.py (unit tree, per the AC correction on TASK-25.1.6.1). TestGenerateGroupMembersReportBoundary pins all three Sheets calls positionally: get_sheet(file_id, sheet_name), batch_update(file_id, exact addSheet request dict), batch_update_values(file_id, "{name}!A1", values). TestGenerateGroupMembersReportBehaviour pins the 50-character sheet-name truncation applied to BOTH the "Group Name" cell and the range, and the exact values matrix. Those behaviour assertions must survive your migration.

Your AC#3 targets the blanket "except Exception: sheet = None". The characterization tests pin its consequences precisely, so you can see what you are changing: get_sheet raising is swallowed, sheet becomes None, the addSheet batch_update path runs, and the report still completes with its success respond(). A separate test pins that a raising batch_update is ALSO swallowed (logged only) while batch_update_values still runs. Replacing either with classification-based handling is an intentional behaviour change to name in your notes.

3. FOLLOW-UP REGISTERED HERE, FOUND WHILE PLANNING TASK-25.1.6.1, NOT FIXED THERE (tests-only task). modules/aws/spending.py::update_spending_data declares spreadsheet_id=SPENDING_SHEET_ID as a DEFAULT ARGUMENT, evaluated at import time. The sheet id is therefore frozen at process start and unaffected by any later config resolution, and patching the module attribute in tests does not change it (which is why every test must pass spreadsheet_id explicitly). execute_spending_data_update_job calls update_spending_data(spending_data) with no id, so it always uses that frozen value. You own this call site -- fix it when you migrate it (read the config inside the function, or take the id from the adapter/settings slice) rather than carrying the import-time binding across.
---

author: @task-planner
created: 2026-09-02 18:52
---
DEPENDENCY ADDED 2026-09-02 (task-planner): now also depends on TASK-25.1.6.12, the A1 sheet-name quoting fix in modules/reports/google_groups.py, which was found while planning TASK-25.1.6.1. It lands before this migration so you repoint already-correct range construction rather than carrying a live defect across a seam change.

WHAT .12 DELIBERATELY LEAVES FOR YOU, so the two tasks do not collide:
- The blanket "except Exception: sheet = None" around get_sheet and the blanket except around the addSheet batch_update are UNTOUCHED by .12. Your AC#3 still owns replacing them with classification-based handling.
- Resilience around batch_update_values is also left to you. Today nothing wraps it, so one failing group aborts the whole report with no respond() at all. Quoting removes the main cause of that abort but not the fragility; when you rewrite this function error handling, decide explicitly whether a failing group should be skipped and reported rather than aborting the run, and record the decision.
- .12 migrates nothing. Both Sheets call sites in that file are still on integrations.google_workspace.sheets when you pick this up.

WHAT CHANGES UNDER YOU: the range handed to batch_update_values and the ranges handed to get_sheet will be single-quoted (with embedded quotes doubled) through one shared helper, and sheet-title truncation will be collision-safe. TASK-25.1.6.1 defect-probe test asserts the quoted form by then, so treat the quoted range as the expected input shape for your adapter method.
---

created: 2026-09-02 19:40
---
REGISTERED FROM TASK-25.1.6.12 PLANNING 2026-09-02 (task-planner). Three things land in this task's scope when .12 ships. .10 already depends on .12, so nothing new blocks here.

1. TWO HELPERS TRAVEL WITH THE CALL SITE, they do not get re-inlined and they do not move into integrations/. TASK-25.1.6.12 adds `_sheet_title(group_name) -> str` and `_a1_range(sheet_title, cell="") -> str` as module-private helpers in app/modules/reports/google_groups.py. When .10 moves the Sheets call sites onto an adapter, both must move with them into the adapter (or into a shared A1 utility outside the vendor package). Putting A1 range formatting into integrations/google_workspace/sheets.py would be a NEW instance of exactly the business-logic-in-the-vendor-package deviation that TASK-25.1.6 exists to close - do not "helpfully" push it down a layer. _a1_range implements gspread's absolute_range_name semantics: unconditional single quotes, embedded quotes doubled. _sheet_title strips apostrophes and appends a deterministic sha256-derived suffix whenever the title had to be derived (over 50 chars, or an apostrophe removed). Never swap that sha256 for the builtin hash(); str.__hash__ is salted per process, so the sheet title would change on every container restart.

2. THE BOUNDARY ASSERTIONS .10 WILL BE TRANSLATING HAVE MOVED. In app/tests/unit/modules/reports/test_google_groups_report.py, every A1 range assertion becomes the quoted form ("'GroupOne'!A1", "'SRE Team'!A1", read range "'GroupOne'"), while the addSheet request title assertion stays BARE ("GroupOne") - a sheet title is a literal title, not A1 notation. Two tests are renamed: test_should_truncate_sheet_name_to_fifty_characters_in_cell_and_range becomes test_should_derive_a_bounded_sheet_title_for_an_overlong_group_name, and test_should_leave_sheet_names_containing_spaces_unquoted_in_ranges becomes test_should_quote_sheet_names_containing_spaces_in_ranges. Four tests are added (apostrophe handling, two collision cases, determinism across two invocations). The respond-message, values-matrix, call-count and call-ordering assertions are untouched, so .10's "characterization tests pass unchanged or each change is named" bar is unaffected by .12.

3. WHAT .12 DELIBERATELY LEFT FOR THIS TASK, unchanged from the existing scope fence: the blanket "except Exception: sheet = None" around get_sheet and the blanket except around the addSheet batch_update are still there for .10 AC#3 to replace with classify_google_error-based handling; and batch_update_values is still unwrapped, so one bad group still aborts the whole report with no respond() to the user. Quoting removes the main CAUSE of that abort but not the fragility - skip-and-report resilience remains .10's call, since .10 is rewriting that error handling anyway.

ONE OPEN QUESTION HANDED OVER RATHER THAN DECIDED IN .12: the Group Name cell (:96 today) carries the DERIVED sheet title, so for an overlong or apostrophe-bearing group the human-readable cell now shows a hash suffix. Putting the full group["name"] in that cell and keeping the derived value only for the title and the range would be strictly more useful, but it is an unrequested behaviour change. If it is not taken as a two-line follow-up before .10, fold it in here.
---

created: 2026-09-02 19:47
---
FORWARD NOTE FROM TASK-25.1.6.12's APPROVAL 2026-09-02 (human). TASK-25.1.6.12 is approved as planned, with an attached instruction to reassess its fix once app/modules/reports/google_groups.py's consumer moves to the app/packages/<feature>/ architecture. That migration has no owning task today, so the note is registered here as the nearest downstream owner of this call site.

Two items to carry, extending the earlier "the two helpers travel with the call site" comment on this task:

1. In the package endstate, _a1_range and _sheet_title belong in the feature's Sheets adapter under app/packages/<feature>/adapters/, next to the try/except plus classify_google_error boundary this task builds. _a1_range is the piece worth lifting to a shared primitive if a second feature ever needs A1 quoting; _sheet_title is report-specific domain logic and stays with the feature. Neither goes into app/integrations/google_workspace/ at any point.

2. The 50-character bound, the sha256 suffix and the apostrophe strip all exist because a user-controlled Google Group display name is being used as a sheet identifier. A feature package with a real domain type for a group could carry a stable identifier separately from the display label, removing the need for the suffix and freeing the Group Name cell to show the full untruncated name. That is the same open question already flagged on this task; it resolves cleanly at the package boundary rather than in a legacy module.
---

author: @task-planner
created: 2026-09-03 21:30
---
YOU INHERIT A time.sleep RATE-LIMITER - FINDING FROM TASK-25.1.6.4 PLANNING (2026-09-03, task-planner).

modules/reports/google_groups.py:127 ends every group iteration with time.sleep(1.1). Facts established while planning .4:

- IT PACES THE SHEETS CALLS, NOT THE DIRECTORY CALLS. The Directory member fetch is a separate earlier loop (:76-85) with no sleep at all. The sleep sits at the bottom of the sheet loop (:87-127), which issues sheets.get_sheet, optionally sheets.batch_update (addSheet) and sheets.batch_update_values per group. 1.1s per iteration is roughly 54 write requests/minute - a hand-rolled guard against the Sheets write quota.
- THERE IS NO SDK-NATIVE RETRY BEHIND IT TODAY. integrations/google_workspace/client.py:154 execute_google_api_request calls request.execute() with NO num_retries argument. So those Sheets calls have zero backoff, and the sleep is currently the only 429 protection the report has.
- .4 THEREFORE LEAVES IT IN PLACE (human decision, recorded as D6 in .4's plan and pinned by .4's AC#3). Removing it before the Sheets calls gain retry would be a regression, not a cleanup.

WHAT THIS MEANS FOR YOU. When you move these Sheets call sites onto an adapter per decisions/outbound-clients.md ("SDK-native resilience configured once", "no hand-rolled retry loops"), pass num_retries at .execute() the way infrastructure/directory/google.py already does (google.py:108 and :503 etc. pass _NUM_RETRIES), and THEN delete the sleep in the same PR. Note that googleapiclient's num_retries is reactive exponential backoff on 429/5xx, which is a different mechanism from a proactive pacer - state that swap explicitly in the PR and confirm the report still completes for the real group count.

TEST TO UPDATE WHEN YOU DO: app/tests/unit/modules/reports/test_google_groups_report.py patches modules.reports.google_groups.time.sleep and asserts test_should_pause_once_per_surviving_group. That assertion is the thing to delete when the sleep goes, not to weaken.
---

created: 2026-09-08 14:37
---
ORDERING UPDATE (2026-09-08): run after .6.9 and the A1 bug fix. Sheets is last among the legacy surface migrations because the Google Groups report is a shared consumer; this keeps its remaining change set isolated and preserves the bug-fix characterization.
---

created: 2026-09-08 14:44
---
SCOPE UPDATE (2026-09-08): the legacy Google Groups report is unused and is being deleted, not migrated. TASK-25.1.6.12 is no longer a prerequisite because its A1-range fix belongs only to the discarded report module. Keep incident-folder and AWS-spending as the live Sheets migration scope.
---
<!-- COMMENTS:END -->
