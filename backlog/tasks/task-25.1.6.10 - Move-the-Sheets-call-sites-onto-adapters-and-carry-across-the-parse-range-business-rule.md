---
id: TASK-25.1.6.10
title: >-
  Retire sheets.py: introduce a Spreadsheet infrastructure capability and
  migrate live consumers
status: To Do
assignee: []
created_date: '2026-09-02 15:03'
updated_date: '2026-09-09 15:29'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.9
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - decisions/migration.md
  - decisions/testing.md
parent_task_id: TASK-25.1.6
priority: medium
ordinal: 141000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR TASK (retitled and rescoped 2026-09-09 during planning, human-directed). Originally scoped as a single slice moving the Sheets call sites onto feature adapters and deleting the report module. Planning found that Sheets, like Drive before it, has two independent live feature consumers - the incident feature (modules/incident/incident_folder.py, 4 call sites) and AWS spending reporting (modules/aws/spending.py, 1 call site). Per decisions/layers.md's promote-on-second-consumer rule, applied proactively exactly as TASK-25.1.6.8 did for Drive, Sheets graduates directly to a Path A infrastructure capability instead of growing a feature-owned adapter that would be promoted later.

KEY DECISIONS TAKEN AT PLANNING TIME (2026-09-09, human-directed):
1. The capability is vendor-neutral: app/infrastructure/spreadsheets/, SpreadsheetProvider, get_spreadsheet_provider(). Not 'sheets' - that is Google vocabulary, and directory/ and drive/ set the naming precedent.
2. Rich grid reads are IN the Protocol via a canonical frozen SheetCell(formatted_value, link). The incident feature recovers a Slack channel id from a cell hyperlink; a values-only contract cannot express that. Portability holds under decisions/layers.md's two-provider test (Microsoft Graph's workbookRange exposes text and formulas, so a second provider populates link by parsing HYPERLINK).
3. A1 notation strings cross the Protocol. sheet!range addressing is a cross-vendor spreadsheet convention, not a vendor DSL like Drive's q= language that was correctly rejected for DriveProvider.
4. No feature adapters. Both live consumers call get_spreadsheet_provider() directly from their legacy modules, following the Directory precedent (TASK-25.1.6.4/.5). The Drive precedent needed adapters only because Google appProperties had to stay out of the vendor-neutral contract; nothing equivalent exists here.
5. No delegated_user_email on the Protocol. No Sheets caller passes one and client._build_service already defaults the subject to SRE_BOT_EMAIL, so the Google auth subject never enters the vendor-neutral contract.
6. The unused legacy report feature is deleted, not migrated. modules/reports/core.py::reports_command has zero callers repo-wide and is absent from _register_legacy_handlers(), so the whole package is unreachable dead code.

DEVIATION FOUND AND OWNED HERE: integrations/google_workspace/client.py::classify_google_error maps only {404}, {401,403} and {429,5xx} and re-raises everything else. The 'Unable to parse range' outcome that modules/incident/incident_folder.py depends on is an HTTP 400, so it would escape the Path A boundary. The Google Sheets implementation maps that specific 400 onto OperationStatus.NOT_FOUND before delegating to classify_google_error; the shared classifier is not modified, so Directory/Drive/Docs/Calendar classification is untouched.

FIVE CHILDREN, in dependency order:
- TASK-25.1.6.10.1 - delete the dead app/modules/reports/ package plus the Google resources config field it orphans. Independent; removes 3 Sheets sites, 2 legacy Drive sites, and the last time.sleep pacer.
- TASK-25.1.6.10.2 - build app/infrastructure/spreadsheets/ (SpreadsheetProvider Protocol, GoogleSpreadsheetProvider, SheetCell, settings, factory). Touches no consumer; does not delete sheets.py.
- TASK-25.1.6.10.3 - migrate modules/incident/incident_folder.py onto the provider, keep the parse-range rule caller-side, and fix four live incident status spreadsheet defects found while planning (the /sre incident show status change never reaching the spreadsheet, its silent no-match failure, its unconditional success message, and an inconsistent dev-channel slug on the recreate path).
- TASK-25.1.6.10.4 - migrate modules/aws/spending.py, fix its import-time spreadsheet-id binding, and delete integrations/google_workspace/sheets.py plus its tests.
- TASK-25.1.6.10.5 - retire integrations/google_workspace/google_drive.py (inherits the original AC#7, whose premise was stale): re-home the incident appProperties metadata operations as real Path B adapter code and relocate DRIVE_SCOPES.

This task closes when all five are Done. Its own remaining direct work is nil.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All five children (TASK-25.1.6.10.1 through .10.5) are Done
- [ ] #2 app/infrastructure/spreadsheets/ exists as a vendor-neutral Path A capability (SpreadsheetProvider Protocol, GoogleSpreadsheetProvider, SheetCell model, settings, cached factory) and no Google response key or auth subject crosses its contract
- [ ] #3 app/integrations/google_workspace/sheets.py and its test file are deleted with zero remaining production references; both live consumers resolve the capability through get_spreadsheet_provider()
- [ ] #4 The whole app/modules/reports/ package and its tests are deleted, no report behavior is migrated or recreated, and the 1.1s time.sleep pacer goes with it
- [ ] #5 The incident parse-range business rule remains caller-side, get_incidents_from_sheet still distinguishes an empty sheet from a failed read, and the four incident status spreadsheet defects are fixed with tests
- [ ] #6 app/integrations/google_workspace/google_drive.py and its test file are deleted, with DRIVE_SCOPES relocated out of the vendor mirror and the incident appProperties metadata operations re-homed to feature-owned Path B adapter code; DriveProvider is not widened
- [ ] #7 Focused tests, ruff, mypy, and app/bin/check_sdk_typing.py pass for every child
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

created: 2026-09-08 18:59
---
AC#7 added 2026-09-08 (task-planner, during TASK-25.1.6.8 planning). TASK-25.1.6.8.2/.8.3 migrate all live incident/role Drive consumers but cannot delete google_drive.py themselves — modules/reports/google_groups.py (deleted only by this task's AC#3) keeps calling google_drive.find_files_by_name/create_file until then. This task is therefore the one that reaches a true zero-production-reference state and should perform the actual file deletion.
---

created: 2026-09-08 23:14
---
IMPACT NOTE FROM TASK-25.1.6.8.3 PLANNING (2026-09-08, task-planner): AC#7's premise that google_drive.py's last two call sites live in modules/reports/google_groups.py is now stale. TASK-25.1.6.8.2 shipped packages/incident/drive/adapters/google_drive.py with deliberate pass-throughs to the legacy module (list_metadata, add_metadata, delete_metadata, and the incident-template health check), and packages/incident_draft/adapters/google_docs.py plus infrastructure/drive/google.py import DRIVE_SCOPES from it. Deleting google_drive.py therefore also requires re-homing those metadata operations (Google appProperties stays out of the vendor-neutral DriveProvider per decisions/layers.md) and relocating DRIVE_SCOPES. TASK-25.1.6.8.3 (packages/talent Drive adapter) adds no new reference: it uses DriveProvider only.
---

author: @task-planner
created: 2026-09-09 15:06
---
DECOMPOSED, RETITLED AND ACs REPLACED 2026-09-09 (task-planner, human-approved). Recording the replacement explicitly per the backlog-task-workflow rule against silently reshaping ACs.

TITLE: 'Migrate live Sheets consumers and delete the legacy Google Groups report module' -> 'Retire sheets.py: introduce a Spreadsheet infrastructure capability and migrate live consumers'.

THE SEVEN PREVIOUS ACs WERE REPLACED WHOLESALE by seven coordinator-level ones. Where the old ones went:
- old AC#1 (consumers use get_sheets_service with adapter-owned classification) -> superseded: the architecture changed from feature adapters to a Path A capability, so consumers now resolve get_spreadsheet_provider(). Owned by .10.2/.10.3/.10.4.
- old AC#2 (parse-range behavior caller-specific) -> .10.3, strengthened with the empty-vs-failed distinction.
- old AC#3 (delete google_groups.py and its tests) -> .10.1, widened to the whole modules/reports package plus its orphaned config field.
- old AC#4 (delete sheets.py) -> .10.4.
- old AC#5 (remove the time.sleep loop) -> .10.1.
- old AC#6 (gates pass) -> per-child, plus coordinator AC#7.
- old AC#7 (delete google_drive.py) -> .10.5, with its stale premise corrected (see comment #9 on this task).

FOUR PRE-REGISTERED ITEMS FROM SIBLING PLANNING WERE ALL CARRIED, NONE DROPPED:
- The spending.py import-time SPENDING_SHEET_ID default-argument defect (registered by .1 planning, comment #1 item 3) -> .10.4.
- The report module's blanket except Exception handling and skip-and-report question (comments #2, #3) -> moot: the module is deleted, not migrated.
- The _a1_range / _sheet_title helpers that TASK-25.1.6.12 shipped and that were to 'travel with the call site' (comments #3, #4) -> moot for the same reason; .10.1's description records that the fix is superseded by deletion, not regressed.
- The time.sleep(1.1) pacer and its num_retries swap (comment #5) -> .10.1 deletes it with the module. Note the SDK-native retry it was waiting for is not needed: the surviving live Sheets consumers never had a pacer.

NEW FINDING THAT SHAPES .10.2 AND .10.3: classify_google_error re-raises HTTP 400, and 'Unable to parse range' IS a 400 - so the one error case a live consumer depends on would escape the Path A boundary. Handled inside the Google Sheets implementation without touching the shared classifier. Full rationale in the rewritten description.

PRODUCTION BUG FOUND WHILE PLANNING, FOLDED INTO .10.3 (human-directed): changing an incident's status through the /sre incident show modal updates DynamoDB and the incident document but never the spreadsheet, which stays 'In Progress'. Root cause is exact: add_new_incident_to_list writes column E as =HYPERLINK(url, '#{slug}') with no 'incident-' prefix; incident_status.py:57 normalizes with return_channel_name() but information_update.py:313 passes the raw DB channel_name, so the row scan never matches and update_spreadsheet_incident_status returns False silently. Three related defects (silent no-match, unconditional success message, inconsistent dev-channel slug on the recreate path) were approved into the same slice.
---

author: @task-planner
created: 2026-09-09 15:29
---
REVIEW ROUND 2 OUTCOME 2026-09-09 (human-directed). Three answers, two new tasks outside this coordinator, and one AC change on a child.

1. NO warmup/health_check ON SpreadsheetProvider. Dropped from .10.2 (AC and plan). Rationale in .10.2's comment; the broader convention question - does connectivity warmup belong to the vendor SDK client rather than to each capability Protocol - is now TASK-82, which also owns reconciling DirectoryProvider and DriveProvider. .10.2 must not pre-empt it with a Sheets-specific answer.

2. NO per-call num_retries ANYWHERE IN THIS SERIES. New TASK-25.1.6.13 (sibling under TASK-25.1.6) configures google-api-python-client retry once at construction in client.py via requestBuilder and deletes the 12 per-call arguments plus two duplicate _NUM_RETRIES constants already in infrastructure/directory/google.py and infrastructure/drive/google.py. It is now a dependency of .10.2 and .10.5, the two children that touch the SDK. Empirically verified against 2.198.0 so nobody re-derives it: execute(num_retries=) is the SDK's genuine built-in retry, build(num_retries=) only retries the discovery fetch, and build(requestBuilder=) is the real construction-time seam.

3. DO NOT CARRY DRIFT ACROSS THE SEAM. .10.4's failure semantics are decided rather than deferred: today's uncaught HttpError propagation out of the spending job is drift, not a contract - the migrated call site logs the classified OperationResult and returns, with an explicit one-line comment marking the in-module result handling as a temporary shim until the concern moves into a feature package. Its 'decide during implementation' AC was replaced accordingly.

STANDING PRINCIPLE FOR THE REMAINING CHILDREN, from the human: infrastructure/drive/ and infrastructure/directory/ are a STRUCTURAL template (file split, settings/factory shape, helper naming), not a behavioral one. Existing code may be outdated; where it diverges from decisions/outbound-clients.md or decisions/sdk-typing.md, fix the divergence or route around it rather than copying it. Temporary shims inside frozen legacy modules are acceptable and should be labelled as such, since they are removed when those features are rearchitected into packages.
---
<!-- COMMENTS:END -->
