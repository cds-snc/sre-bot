---
id: TASK-25.1.6.1
title: >-
  Add characterization tests for the untested Google Workspace call sites before
  any adapter work
status: To Do
assignee: []
created_date: '2026-09-02 14:58'
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
- [ ] #1 app/tests/modules/reports/test_google_groups.py exists and covers every Google call site in app/modules/reports/google_groups.py: the Directory list_groups/list_group_members pair, the sheets.get_sheet call including its blanket-except fallback to None, and the Drive find_files_by_name/create_file calls
- [ ] #2 app/modules/aws/spending.py's Sheets call sites have characterization coverage asserting today's request arguments and returned shape
- [ ] #3 Failure paths are pinned, not just happy paths: for each file, a raising SDK call is exercised and the test asserts today's actual observable outcome (swallowed to None, propagated, or partial result), so a later behaviour change is visible as a test diff rather than a silent regression
- [ ] #4 No production file is modified by this task (git diff touches app/tests/** only)
<!-- AC:END -->
