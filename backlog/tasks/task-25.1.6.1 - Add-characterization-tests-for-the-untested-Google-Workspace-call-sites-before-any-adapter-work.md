---
id: TASK-25.1.6.1
title: >-
  Add characterization tests for the untested Google Workspace call sites before
  any adapter work
status: To Do
assignee: []
created_date: '2026-09-02 14:58'
updated_date: '2026-09-02 18:54'
labels:
  - clients
  - phase-3
  - testing
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/testing.md
  - app/modules/reports/google_groups.py
  - app/modules/aws/spending.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 132000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
GATE TASK for the TASK-25.1.6 decomposition. No production change; tests only.

TASK-25.1.3's and TASK-25.1.5's implementation notes both recorded the same hole: two production files that call Google Workspace vendor modules have NO automated coverage of those call sites, before or after their dispatcher migration.

- app/modules/reports/google_groups.py has NO test file at all. It calls google_directory.list_groups, google_directory.list_group_members, sheets.get_sheet (wrapped in a blanket `except Exception: sheet = None`), google_drive.find_files_by_name and google_drive.create_file.
- app/modules/aws/spending.py has no coverage of its Sheets call sites (app/tests/modules/aws/test_spending_handler.py covers a different function).

Every sibling under TASK-25.1.6 changes the error-handling shape of exactly these call sites - that is the whole point of moving classification from the vendor package into an adapter. Doing that against zero coverage is unguarded. TASK-25.1.3's notes say it explicitly: do not treat 'existing tests pass' as evidence of safety for these two files.

Write characterization tests FIRST that pin today's observable behaviour, including the ugly parts (the blanket except that yields sheet = None, whatever partial results a mid-loop failure produces). These tests are the contract that the later adapter slices must either preserve or consciously and visibly change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/tests/unit/modules/reports/test_google_groups_report.py exists (unit layer per decisions/testing.md, NOT the legacy app/tests/modules tree) and pins today request arguments at all seven Google call sites in app/modules/reports/google_groups.py: google_drive.find_files_by_name, google_drive.create_file, google_directory.list_groups, google_directory.list_group_members, sheets.get_sheet, sheets.batch_update (the addSheet request) and sheets.batch_update_values
- [ ] #2 Assertions are split into a BEHAVIOUR group (what the module computes and emits: respond strings for the unset-folder, no-groups and success branches; the AWS- name exclusion; the 50-character sheet-name truncation; the {name}!A1 range; the header-plus-members values matrix) and a BOUNDARY group (arguments handed to the vendor modules), so later slices can translate the boundary group while the behaviour group must keep passing unchanged
- [ ] #3 Failure and partial-result paths are pinned for google_groups.py, not just happy paths: the blanket except around sheets.get_sheet yielding sheet=None and the addSheet fallback; a raising sheets.batch_update being swallowed while batch_update_values still runs; a raising Drive or Directory call propagating uncaught; and the observable partial state after a mid-loop failure (file already created, N sheets already written)
- [ ] #4 app/tests/unit/modules/aws/test_spending_handler.py is EXTENDED (not duplicated) to close its real gap: the exact values matrix crossing sheets.batch_update_values (header row plus DataFrame rows), the empty-DataFrame case, spreadsheet_id="" skipping the call, and a raising Sheets call propagating out of update_spending_data
- [ ] #5 Tests obey decisions/testing.md: marked unit, deterministic (freezegun for the date-derived filename, time.sleep patched so the per-group 1.1s pause does not enter the runtime budget), no network, and no docstring references to task ids or plan steps
- [ ] #6 No production file is modified by this task (git diff touches app/tests/** only)
- [ ] #7 Seam-churn control is implemented so the three sibling rewires are cheap: ONE fixture owns all patching, no test reads mock.call_args directly (all assertions go through named accessor helpers that normalise the seam), and the three respond() message literals live in single module-level constants
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (2026-09-02, verified against current code, not the task prose alone)

SUBJECT 1 -- app/modules/reports/google_groups.py (107 LOC). No test file exists anywhere for it
(find app/tests -path "*reports*" returns zero). Reached from modules/reports/core.py:42, the
/sre reports google-groups-members Slack command. Seven Google call sites:
  :37  google_drive.find_files_by_name(filename, FOLDER_REPORTS_GOOGLE_GROUPS)
  :41  google_drive.create_file(filename, FOLDER_REPORTS_GOOGLE_GROUPS, "spreadsheet")
  :47  google_directory.list_groups()
  :61  google_directory.list_group_members(group["email"])
  :72  sheets.get_sheet(file["id"], group_sheet_name)          <- wrapped in blanket except -> None
  :90  sheets.batch_update(file["id"], {"requests":[{"addSheet":...}]})  <- except Exception -> log only
  :100 sheets.batch_update_values(file["id"], f"{name}!A1", values)
Control flow worth pinning, in order: falsy folder -> respond + return before any Google call;
filename is date-derived; file is created BEFORE the empty-groups check, so a run with zero groups
still creates a spreadsheet; groups whose "name" contains "AWS-" are filtered out; member collection
completes for ALL groups before ANY sheet write begins; sheet name truncated to 50 chars and reused
both as the "Group Name" cell and as the "{name}!A1" range; time.sleep(1.1) per group.

SUBJECT 2 -- app/modules/aws/spending.py. Exactly ONE Sheets call site: :190
sheets.batch_update_values(spreadsheetId=..., cell_range="Sheet1", values=..., valueInputOption=...)
inside update_spending_data. Contrary to the task description, this is NOT uncovered:
app/tests/unit/modules/aws/test_spending_handler.py:102-133 already asserts spreadsheetId,
cell_range, valueInputOption and the skip-when-id-falsy branch (TASK-25.1.3 notes looked at
app/tests/modules/aws/, which does not exist). Real gap: the values matrix crossing the boundary is
never asserted, and there is no failure-path coverage. See the AC-corrections comment on this task.

SUSPECTED PRODUCTION DEFECT FOUND WHILE PLANNING -- PINNED HERE, FIXED ELSEWHERE
google_groups.py:97 builds an A1 range by interpolating a Google Group DISPLAY NAME straight into
f"{group_sheet_name}!A1" with no quoting, and :72 passes the same bare name as get_sheet ranges=.
Google Sheets A1 notation requires a sheet name containing spaces or special characters to be
wrapped in single quotes (with embedded quotes doubled); unquoted, the API rejects the request with
400 "Unable to parse range". Group display names routinely contain spaces. Corroborating evidence,
not speculation: (a) every OTHER range in this repo is a hardcoded space-free literal --
incident_folder.py:271 "Sheet1!A:A", :305 "Sheet1", :318 f"{sheet_name}!D{i+1}" over a "Sheet1"
literal, spending.py:192 "Sheet1" -- so this is the only user-controlled sheet name in an A1 range
repo-wide; (b) TASK-25.1.3 relocated a live "Unable to parse range" swallow for the incidents sheet,
so this app demonstrably hits that exact error class; (c) tests/factories/google.py emits space-free
names like "group-name1", so any test built on the factory would never surface it.
Likely observable impact: get_sheet 400s and is swallowed by the blanket except -> sheet=None -> the
addSheet path runs -> if the sheet already exists that 400s too and is swallowed -> batch_update_values
400s and PROPAGATES, because nothing wraps it. The Slack command then dies with no respond() at all.
NOT FIXED IN THIS TASK (this is a tests-only gate; AC#6 forbids production edits). This task PINS
todays unquoted behaviour so the defect is visible and the fix is a two-assertion diff. See the
comment on this task for the proposed fix task and its ordering ahead of TASK-25.1.6.10.

PLACEMENT AND TOOLING
- app/tests/modules/ is the legacy tree; decisions/testing.md mandates unit/integration/smoke, and
  every maintained module test lives under app/tests/unit/modules/<area>/. New file goes to
  app/tests/unit/modules/reports/.
- app/tests/unit/modules/ has NO __init__.py while each child dir (aws, incident, role, ...) does.
  Mirror that: add app/tests/unit/modules/reports/__init__.py only. Do NOT add one to the parent --
  it would change package naming for the existing sibling test packages.
- No pytest-mock in this repo. Use unittest.mock.patch, matching test_spending_handler.py house
  style. freezegun==1.5.5 is available and is the blessed clock tool per decisions/testing.md.

MOCK SEAM -- deliberate, and the thing the later slices inherit
Patch the VENDOR MODULE OBJECTS as bound in the module under test:
  patch("modules.reports.google_groups.google_directory" / ".google_drive" / ".sheets")
  patch("modules.aws.spending.sheets")
That is todays real boundary, so it is what can pin todays request arguments. It is explicitly NOT
the target seam: TASK-25.1.6.4 replaces the Directory calls with DirectoryProvider, .8 with an
incident Drive adapter, .10 with a Sheets adapter. MagicMock module doubles rather than Protocol
fakes -- decisions/testing.md last-choice double -- ACCEPTED BY THE HUMAN 2026-09-02 for this task,
on the grounds that the subjects are legacy app/modules/* whose collaborators are plain function
modules with no Protocol, and inventing one would mean building the very adapters the sibling slices
exist to build.

SEAM-CHURN CONTROL -- the design constraint that decides what .4/.8/.10 cost
Three sibling slices will each rewire this one file. Write it so each rewire is a handful of edits,
not a rewrite. Follow the precedent TASK-25.1.5.1 set with _drive_resource_fake plus its
_copy_request accessor, which its own notes credit with making TASK-25.1.6.6 cheap.
1. ONE fixture owns all patching (report_deps). No test patches anything itself. That fixture is the
   single rewire point per sibling.
2. NO test reads mock.call_args directly. Every assertion goes through a small set of ACCESSOR
   HELPERS that normalise the seam into repo-local shapes:
     _file_lookup(deps)      -> tuple[str, str]                  (name, folder_id)
     _groups_listed(deps)    -> int                              (call count; args are seam-shaped)
     _members_requested(deps)-> list[str]                        (group keys, in order)
     _sheet_writes(deps)     -> list[tuple[str, str, list[list]]] (spreadsheet_id, range, values)
     _sheets_created(deps)   -> list[tuple[str, str]]            (spreadsheet_id, addSheet title)
   When .4 swaps Directory for DirectoryProvider only _groups_listed/_members_requested change; when
   .8 swaps Drive only _file_lookup changes; when .10 swaps Sheets only _sheet_writes/_sheets_created
   change. The ~12 behaviour assertions do not move. Without accessors each sibling rewrites ~15
   assertion sites and has to re-judge each one against its "pass unchanged or name the change" AC.
3. Message literals get ONE indirection: module-level _MSG_FOLDER_UNSET / _MSG_NO_GROUPS /
   _MSG_SUCCESS. Assert respond.assert_called_once_with(_MSG_SUCCESS) -- exact, because the message
   is the ONLY thing distinguishing the no-groups branch from the success branch, so substring or
   assert_called matching would let a branch swap pass silently and the gate would stop gating. A
   cosmetic reword then costs one line, not N.
4. Keep the BOUNDARY group thin and never restate a fact the BEHAVIOUR group already asserts. The
   boundary group is the disposable half; duplication there is duplicated migration cost.
5. Do not parametrize across the seam. Explicit tests translate; parametrized ones have to be
   untangled first.

ORDERED STEPS

1. Create app/tests/unit/modules/reports/__init__.py (empty).

2. Create app/tests/unit/modules/reports/test_google_groups_report.py.
   Module-level patch-target constants (_DIRECTORY/_DRIVE/_SHEETS/_SLEEP), the three _MSG_ constants,
   the five accessor helpers above, and ONE shared fixture report_deps which: patches the three
   vendor modules plus time.sleep; monkeypatches FOLDER_REPORTS_GOOGLE_GROUPS to "FOLDER1"; and
   installs explicit defaults -- find_files_by_name -> [], create_file -> {"id": "FILE1"},
   list_groups -> two plain group dicts with name/email, list_group_members -> two member dicts with
   email/role, get_sheet -> {} (an EXPLICIT falsy dict; a bare MagicMock return is truthy and would
   silently skip the addSheet branch), batch_update -> {}, batch_update_values -> {}. Yield a simple
   namespace plus a MagicMock respond. The fixture is the single place any test overrides a value.

   class TestGenerateGroupMembersReportBehaviour  (must survive .4/.8/.10 unchanged)
     - unset folder: do NOT use the fixture patch of the constant; assert respond receives
       _MSG_FOLDER_UNSET and that all three vendor mocks recorded zero calls.
     - success: respond called once with _MSG_SUCCESS.
     - a group whose name contains "AWS-" is excluded: no sheet write for it.
     - list_groups returns only excluded groups (or []): respond receives _MSG_NO_GROUPS AND
       create_file was still called first -- pins the create-before-check ordering wart.
     - a 60-character group name is truncated to 50 in BOTH the "Group Name" values row and the
       "{name}!A1" range.
     - values matrix equals [["Group Name", name], ["Email", "Role"], [m.email, m.role], ...] in
       member order.
     - time.sleep called once per surviving group with 1.1.
     - GROUP NAME CONTAINING A SPACE (the defect probe): a group named "SRE Team" produces range
       "SRE Team!A1" and get_sheet ranges "SRE Team" -- UNQUOTED, as today. One short comment marks
       this as pinned-not-endorsed and points at the fix task. This is the assertion the fix task
       flips to "\x27SRE Team\x27!A1".

   class TestGenerateGroupMembersReportBoundary  (translated by .4/.8/.10)
     - under freeze_time("2026-05-04"), _file_lookup is ("groups_report_2026-05-04", "FOLDER1").
     - no existing file -> create_file(filename, "FOLDER1", "spreadsheet"); existing file ->
       create_file NOT called and files[0]["id"] is the spreadsheet id used by every later Sheets call.
     - list_groups called once with no arguments; list_group_members called once per surviving group
       with that group email, positionally.
     - get_sheet(file_id, sheet_name) positional; batch_update(file_id, exact addSheet request dict);
       batch_update_values(file_id, range, values) positional.

   class TestGenerateGroupMembersReportFailureModes
     - get_sheet raises RuntimeError -> swallowed by the blanket except, sheet is None, addSheet IS
       called, run completes with _MSG_SUCCESS.
     - get_sheet returns a truthy dict -> batch_update NOT called.
     - batch_update raises -> swallowed, the values write still happens, run completes.
     - find_files_by_name raises -> propagates (pytest.raises); respond never called; no Directory or
       Sheets call made.
     - list_groups raises -> propagates; create_file had ALREADY run (partial side effect pinned).
     - list_group_members raises on the second group -> propagates; ZERO sheet writes (member
       collection precedes all writes) -- todays partial state is "file created, no sheets".
     - batch_update_values raises on the second group -> propagates with NO respond() at all; the
       FIRST group sheet was already written. This is the exact shape the suspected A1-quoting defect
       takes in production, so it doubles as that defects regression guard.

3. Extend app/tests/unit/modules/aws/test_spending_handler.py. Do not restructure or rename the
   existing four tests; append:
     - exact values payload: a two-row DataFrame -> call_kwargs["values"] == [columns, row0, row1]
       with the DataFrame own value types.
     - an empty-but-columned DataFrame -> values == [columns] only.
     - spreadsheet_id="" (the value SPENDING_SHEET_ID actually holds under test) also skips the call
       -- the existing test only covers None.
     - batch_update_values side_effect RuntimeError -> propagates out of update_spending_data
       (no try/except exists today).
   Do NOT add a test asserting execute_spending_data_update_job reaches Sheets: it passes the
   def-time-bound default, and :136-167 already pin that delegation with update_spending_data patched.

4. Validate: cd app && uv run pytest tests/unit/modules/reports tests/unit/modules/aws/test_spending_handler.py -q --durations=10
   (confirms collection works for the new package and that the unit budget holds), then
   uv run ruff check . ; uv run mypy . --exclude "(?:^|/)\.venv(?:/|$)" ;
   uv run pytest tests --ignore=tests/smoke.

5. After merge, confirm the pre-registered comments on TASK-25.1.6.4, .8 and .10 still name the
   correct file paths, class names and accessor helper names; correct them if implementation deviated.

AC TRACEABILITY
- AC#1 -> steps 1-2, class TestGenerateGroupMembersReportBoundary (all seven sites).
- AC#2 -> step 2 class split (Behaviour vs Boundary) and step 3 additions.
- AC#3 -> step 2 class TestGenerateGroupMembersReportFailureModes (seven cases, two partial-state).
- AC#4 -> step 3.
- AC#5 -> the shared fixture (time.sleep patch), freeze_time on the filename test, pytest.mark.unit
  on every test, and step 4 --durations check; docstrings describe behaviour and stub strategy only.
- AC#6 -> nothing outside app/tests/** is touched; verified by git diff --stat at review time.
- AC#7 -> the SEAM-CHURN CONTROL section: one fixture, five accessors, three message constants, no
  direct call_args reads.

TEST MATRIX
| Case | File | Class | Asserts |
| happy: full report | test_google_groups_report.py | Behaviour | _MSG_SUCCESS, one write per group |
| boundary: folder unset | same | Behaviour | early respond, zero Google calls |
| boundary: no groups after filter | same | Behaviour | _MSG_NO_GROUPS AND file already created |
| boundary: 60-char name | same | Behaviour | 50-char truncation in cell and range |
| boundary: name with a space | same | Behaviour | unquoted "SRE Team!A1" (defect probe) |
| boundary: existing file found | same | Boundary | create_file not called, files[0] id reused |
| boundary: date-derived filename | same | Boundary | freeze_time, exact _file_lookup |
| failure: get_sheet raises | same | FailureModes | swallowed -> addSheet path -> run completes |
| failure: batch_update raises | same | FailureModes | swallowed -> values write still happens |
| failure: Drive list raises | same | FailureModes | propagates, no respond, no downstream calls |
| failure: Directory list raises | same | FailureModes | propagates, file already created |
| partial: members raises on group 2 | same | FailureModes | propagates, zero writes |
| partial: values write raises on group 2 | same | FailureModes | propagates, no respond, one write done |
| happy: values matrix | test_spending_handler.py | (appended) | [columns, row0, row1] |
| boundary: empty DataFrame | same | (appended) | [columns] only |
| boundary: spreadsheet_id="" | same | (appended) | no Sheets call |
| failure: Sheets raises | same | (appended) | propagates out of update_spending_data |

ASSUMPTIONS AND DOUBTS
- Assumes app/tests/unit/modules/ intentionally lacks __init__.py while its children have one, and
  that adding one only to reports/ collects cleanly. VERIFY by actually running step 4 rather than
  assuming; if collection complains about a duplicate basename, fall back to no __init__.py.
- RESOLVED (human, 2026-09-02): MagicMock module doubles are accepted here; do not spend the task
  inventing Protocol fakes.
- RESOLVED: the exact respond() strings ARE part of the contract, because the message is the only
  observable that distinguishes the branches. Centralised behind three constants so a reword is one
  line -- see SEAM-CHURN CONTROL item 3.
- RESOLVED: group["name"] raising KeyError on a name-less group is NOT pinned. groups.list is called
  with no fields projection, and the Directory API always returns name/email on a group resource, so
  this is a crash on impossible input rather than a designed behaviour. The name-shaped defect worth
  covering turned out to be the A1 quoting one above, which IS pinned.
- The A1-quoting defect is assessed from the Sheets A1 notation rules plus the in-repo corroboration
  listed under SUSPECTED PRODUCTION DEFECT; it is NOT confirmed against live Google here. Confirming
  it is the first step of the fix task, not of this one. Pinning todays unquoted output is correct
  either way: if Google turns out to be lenient the pinned assertion is simply an accurate record.
- These tests deliberately encode behaviour that is WRONG (blanket except, create-file-before-empty-
  check, 1.1s sleep, unquoted A1 range, def-time-bound spreadsheet default). They are a change
  detector, not an endorsement. The correct response to a red characterization test in .4/.8/.10 is
  often to update it and say why.

FOLLOW-UPS NOTED, NOT FIXED (tests-only task)
1. spending.update_spending_data binds spreadsheet_id=SPENDING_SHEET_ID at import time, freezing the
   sheet id at process start. Registered by comment on TASK-25.1.6.10, which owns that call site.
2. The A1-quoting defect above, plus its two neighbours found with it: the 50-char truncation can
   collide two group names onto one sheet title (second silently overwrites the first, and the
   duplicate-title addSheet 400 is swallowed), and nothing wraps batch_update_values so one bad group
   aborts the whole report with no user feedback. Proposed as its own task ahead of TASK-25.1.6.10 --
   see the comment on this task; awaiting human approval to create.

BLAST RADIUS AND ROLLBACK
Zero production LOC, zero production files. Two test files (one new ~400-450 LOC, one extended ~+70)
plus one empty __init__.py. Nothing ships behaviour; a single git revert removes the guard and
nothing else. No terraform, CI, settings or migration ordering.

SIZE GATE VERDICT: FITS ONE PR. Production diff is 0 files / 0 LOC, one subsystem (tests), no
mechanical-plus-behaviour mixing, revert-safe. No decomposition required.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-02 17:14
---
AC CORRECTIONS 2026-09-02 (task-planner), after grounding the task against current code. Three of the four ACs carried inaccurate premises; recording the replacement explicitly rather than quietly reshaping them.

1. AC#1 TEST PATH WAS WRONG FOR THIS REPO. It named app/tests/modules/reports/test_google_groups.py. app/tests/modules/ is the LEGACY tree; decisions/testing.md mandates one tree with unit/integration/smoke layers, and every maintained module test lives under app/tests/unit/modules/<area>/ (atip, aws, incident, role, secret, sre). Corrected to app/tests/unit/modules/reports/test_google_groups_report.py.

2. AC#1 CALL-SITE LIST WAS INCOMPLETE. It named five sites. grep -n on app/modules/reports/google_groups.py shows SEVEN: google_drive.find_files_by_name:37, google_drive.create_file:41, google_directory.list_groups:47, google_directory.list_group_members:61, sheets.get_sheet:72, sheets.batch_update:90 (the addSheet request), sheets.batch_update_values:100. The two missing ones are Sheets writes that TASK-25.1.6.10 will migrate, so leaving them unpinned would defeat the point of this gate.

3. AC#2 PREMISE WAS PARTLY WRONG. The task says modules/aws/spending.py has no coverage of its Sheets call sites, citing TASK-25.1.3 notes. It has exactly ONE Sheets call site (sheets.batch_update_values:190 in update_spending_data), and app/tests/unit/modules/aws/test_spending_handler.py:102-133 ALREADY asserts spreadsheetId, cell_range and valueInputOption plus the skip-when-no-id branch. TASK-25.1.3 notes looked at app/tests/modules/aws/ (which does not exist) rather than app/tests/unit/modules/aws/. The genuine gap is narrower: the values matrix that actually crosses the boundary (header row plus DataFrame rows) is never asserted, and there is no failure-path coverage. AC#2 narrowed to that gap, and the work extends the existing file rather than creating a duplicate one.

4. AC#2/#3 gained an explicit BEHAVIOUR vs BOUNDARY split (new AC#2). Characterization tests here have two jobs with different lifetimes: assertions about what the module computes and emits must survive every TASK-25.1.6 slice unchanged, while assertions about the vendor-call arguments will legitimately be TRANSLATED when the seam moves to DirectoryProvider (TASK-25.1.6.4), the Drive adapter (.8) and the Sheets adapter (.10). Splitting them into labelled groups is what makes those siblings ACs (characterization tests pass unchanged, or each intentional change is named) checkable rather than a judgement call.

Nothing was removed from scope; AC#4 (no production file modified) is unchanged and renumbered.
---

author: @task-planner
created: 2026-09-02 18:48
---
SUSPECTED PRODUCTION DEFECT FOUND WHILE PLANNING (2026-09-02, task-planner). Raised for a decision rather than folded into this task, because this is a tests-only gate and AC#6 forbids production edits.

THE DEFECT. app/modules/reports/google_groups.py:97 builds an A1 range by interpolating a Google Group DISPLAY NAME straight into f"{group_sheet_name}!A1" with no quoting, and :72 passes the same bare name as get_sheet ranges=. Google Sheets A1 notation requires a sheet name containing spaces or special characters to be wrapped in single quotes (embedded quotes doubled); unquoted, the API rejects it with 400 "Unable to parse range". Google Group display names routinely contain spaces.

WHY THIS IS NOT SPECULATION.
(a) It is the ONLY user-controlled sheet name in an A1 range repo-wide. Every other range is a hardcoded, space-free literal: incident_folder.py:271 "Sheet1!A:A", :305 "Sheet1", :318 f"{sheet_name}!D{i+1}" over a "Sheet1" literal, spending.py:192 "Sheet1".
(b) TASK-25.1.3 relocated a live "Unable to parse range" swallow for the incidents sheet, so this application demonstrably hits that exact error class in production.
(c) tests/factories/google.py emits space-free names ("group-name1"), so any test built naively on the factory would never surface it -- which is likely why it has survived.

LIKELY PRODUCTION SHAPE. get_sheet 400s and is swallowed by the blanket except -> sheet=None -> the addSheet path runs -> if that sheet already exists the addSheet 400s too and is swallowed by the second except -> batch_update_values 400s and PROPAGATES, because nothing wraps it. The /sre reports google-groups-members command then dies at the first affected group with no respond() at all: the user sees nothing. The two blanket excepts are actively masking the diagnosis.

TWO NEIGHBOURS FOUND WITH IT, same function, same fix window:
- The 50-character truncation at :69-70 can collide two different group names onto one sheet title. The second groups write then silently overwrites the first, and the duplicate-title addSheet 400 is swallowed.
- Nothing wraps batch_update_values, so a single bad group aborts the entire report rather than being skipped and reported.

RECOMMENDATION -- three options considered.
A. Fix it inside this task. REJECTED: destroys the purpose of a characterization gate, breaks AC#6, and mixes a behaviour change into the guard PR.
B. Hand it to TASK-25.1.6.10, which owns this call site. REJECTED as the primary route: .10 is Medium and downstream, so the bug lives on; and it would mix a behaviour fix into a migration PR, which the implementation-planning size gate explicitly separates (mechanical diffs are reviewed for completeness, behaviour diffs for correctness).
C. RECOMMENDED: a small standalone fix task, dependency-ordered AFTER this one and BEFORE TASK-25.1.6.10. Its first step is to confirm the behaviour against the Sheets API (docs plus a targeted check) rather than assume it. Scope: quote the sheet name in both the range and the ranges argument, make truncation collision-safe, and decide whether a failed group should skip-and-report instead of aborting. Estimated production diff well under 50 LOC in one file, one subsystem, trivially revertible.

WHAT THIS TASK DOES ABOUT IT NOW. The plan adds a defect probe to TestGenerateGroupMembersReportBehaviour: a group named "SRE Team" is asserted to produce the unquoted range "SRE Team!A1" today, marked pinned-not-endorsed. The fix task then flips exactly that assertion. The mid-loop batch_update_values failure test in TestGenerateGroupMembersReportFailureModes already pins the abort-with-no-respond shape, so it doubles as the regression guard.

AWAITING HUMAN APPROVAL to create the fix task with --dep TASK-25.1.6.1 --parent TASK-25.1.6 and to add it as a dependency of TASK-25.1.6.10.
---

author: @task-planner
created: 2026-09-02 18:54
---
APPROVED AND CREATED 2026-09-02 (human). The fix task proposed in the previous comment now exists as TASK-25.1.6.12 - "Fix the unquoted A1 sheet-name range in the Google Groups members report" (type bug, High, milestone m-3, parent TASK-25.1.6, ordinal 132500).

WIRING APPLIED: TASK-25.1.6.12 depends on THIS task, and TASK-25.1.6.10 now depends on TASK-25.1.6.7 AND TASK-25.1.6.12. The coordinator TASK-25.1.6 was updated from eleven children to twelve (AC#1 and the Description child list).

WHAT THIS MEANS FOR THIS TASK: nothing changes in its scope. It stays tests-only and AC#6 still forbids production edits. The defect probe in TestGenerateGroupMembersReportBehaviour must still pin todays UNQUOTED range ("SRE Team!A1"), because TASK-25.1.6.12 depends on this task landing first and its AC#5 is defined as flipping exactly that one assertion. Do not pre-emptively assert the quoted form.

Resolves the "awaiting human approval to create" note in FOLLOW-UPS item 2 of the implementation plan.
---
<!-- COMMENTS:END -->
