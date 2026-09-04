---
id: TASK-25.1.6.10
title: >-
  Move the Sheets call sites onto adapters and carry across the parse-range
  business rule
status: To Do
assignee: []
created_date: '2026-09-02 15:03'
updated_date: '2026-09-03 21:30'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.7
  - TASK-25.1.6.12
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
<!-- COMMENTS:END -->
