---
id: TASK-25.1.6.12
title: Fix the unquoted A1 sheet-name range in the Google Groups members report
status: To Do
assignee: []
created_date: '2026-09-02 18:52'
labels:
  - reports
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.1
references:
  - app/modules/reports/google_groups.py
  - decisions/testing.md
  - 'https://developers.google.com/workspace/sheets/api/guides/concepts'
parent_task_id: TASK-25.1.6
priority: high
type: bug
ordinal: 132500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while planning TASK-25.1.6.1 (see the SUSPECTED PRODUCTION DEFECT comment on that task for the full evidence). Split out as its own task rather than folded into a characterization gate or a migration PR, so a behaviour fix is reviewed as a behaviour fix.

THE DEFECT. app/modules/reports/google_groups.py:97 builds an A1 range by interpolating a Google Group DISPLAY NAME straight into f"{group_sheet_name}!A1" with no quoting, and :72 passes the same bare name as the get_sheet ranges argument. Google Sheets A1 notation requires a sheet name containing spaces or special characters to be wrapped in single quotes, with any embedded single quote doubled. Unquoted, the API rejects the request with 400 "Unable to parse range". Google Group display names routinely contain spaces.

EVIDENCE THAT THIS IS REAL, NOT SPECULATION.
(a) It is the only user-controlled sheet name in an A1 range repo-wide. Every other range is a hardcoded, space-free literal: incident_folder.py:271 Sheet1!A:A, :305 Sheet1, :318 an f-string over a Sheet1 literal, spending.py:192 Sheet1.
(b) TASK-25.1.3 relocated a live "Unable to parse range" swallow for the incidents sheet, so this application demonstrably hits that exact error class in production.
(c) tests/factories/google.py emits space-free names like group-name1, so tests built on the factory never surface it, which is likely why it survived.

LIKELY PRODUCTION SHAPE. get_sheet 400s and is swallowed by the blanket except, so sheet becomes None; the addSheet path then runs; if the sheet already exists that 400s too and is swallowed by the second except; finally batch_update_values 400s and PROPAGATES, because nothing wraps it. The /sre reports google-groups-members Slack command dies at the first affected group with no respond() at all, so the user sees nothing. The two blanket excepts are actively masking the diagnosis.

SECOND DEFECT, SAME FIX WINDOW. The 50-character truncation at :69-70 can collide two different group names onto one sheet title. The second group write then silently overwrites the first, and the resulting duplicate-title addSheet 400 is swallowed too.

VERIFY BEFORE CHANGING. The first step is to confirm the quoting rule and the exact failure against the Sheets API documentation and a targeted check, not to assume it. Quoting is valid A1 notation whether or not the API is lenient, so the fix is safe either way, but the task notes must record what was actually confirmed.

EXPLICITLY OUT OF SCOPE, to avoid colliding with TASK-25.1.6.10.
- Do NOT touch the blanket "except Exception: sheet = None" around get_sheet or the blanket except around the addSheet batch_update. TASK-25.1.6.10 AC#3 owns replacing those with classification-based handling.
- Do NOT add resilience around batch_update_values so that one bad group is skipped instead of aborting the report. Quoting removes the main cause of that abort; the remaining resilience question belongs with TASK-25.1.6.10, which is rewriting the error handling in this function anyway. It is registered there by comment.
- Do NOT migrate any call site onto an adapter. This task leaves the seam exactly where it is.

GUARDED BY TASK-25.1.6.1, which is a hard dependency. That task pins todays unquoted output in a named defect probe (a group called SRE Team producing an unquoted range) plus a failure test covering the abort-with-no-respond shape. This fix flips that probe assertion; nothing else in that file should need to change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The quoting rule and the failure mode are confirmed against the Sheets A1 notation documentation before any production edit, and the task notes record what was verified and how
- [ ] #2 The A1 range passed to sheets.batch_update_values wraps the sheet name in single quotes with embedded single quotes doubled, so a group named with spaces, a leading digit or an apostrophe produces a valid range
- [ ] #3 The ranges argument passed to sheets.get_sheet is quoted by the same rule and through the same single helper, so the two call sites cannot drift apart
- [ ] #4 Sheet-title truncation is collision-safe: two group names sharing their first 50 characters no longer resolve to the same sheet title, and a test covers the collision case
- [ ] #5 TASK-25.1.6.1 defect-probe assertion is updated from the unquoted range to the quoted one, and no other assertion in app/tests/unit/modules/reports/test_google_groups_report.py needs to change
- [ ] #6 The blanket excepts around get_sheet and the addSheet batch_update are untouched, and no call site is migrated onto an adapter, leaving TASK-25.1.6.10 scope intact
<!-- AC:END -->
