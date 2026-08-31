---
id: TASK-23.1
title: Delete the Google _next dispatcher generation (zero production consumers)
status: To Do
assignee: []
created_date: '2026-08-31 17:35'
updated_date: '2026-08-31 17:38'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.4
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
parent_task_id: TASK-23
priority: high
ordinal: 125000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Deletes the Google half of the _next dispatcher generation. Fresh grep (2026-08-31) confirms ZERO production consumers: google_service_next.py, google_directory_next.py and gmail_next.py are imported only by each other and by their own tests plus one smoke test.

Scope:
1. Delete app/integrations/google_workspace/google_service_next.py (641 LOC, execute_google_api_call + time.sleep retry loop), google_directory_next.py (638 LOC), gmail_next.py (263 LOC).
2. Delete app/tests/integrations/google_workspace/test_google_service_next.py and test_google_directory_next.py.
3. Resolve app/tests/smoke/google_smoke_test.py, which imports google_directory_next.

Out of scope: integrations/google_workspace/google_service.py's execute_google_api_call and its get_google_api_command_parameters docstring scraper - that is the non-_next generation with 16 live consumer files, owned by TASK-25.1.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/integrations/google_workspace contains no google_service_next.py, google_directory_next.py or gmail_next.py, and repo-wide grep for those three module names returns zero hits outside backlog/ and tmp/
- [ ] #2 The _next-generation execute_google_api_call in google_service_next.py no longer exists; the separate non-_next execute_google_api_call in google_service.py is untouched (TASK-25.1 scope)
- [ ] #3 app/tests/smoke/google_smoke_test.py no longer imports google_directory_next; the Google integration test tree shrinks and no surviving test imports a deleted module
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test green; no production behavior change (deleted modules had zero production consumers)
- [ ] #2 PR references decisions/outbound-clients.md and decisions/sdk-typing.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Pure-deletion slice. No production consumer exists for any of the three modules, so nothing is migrated and no behavior can change. Verified by repo-wide grep on 2026-08-31 (excluding backlog/, tmp/, .mypy_cache, .pytest_cache): the only importers of google_service_next / google_directory_next / gmail_next are each other, their own two test files, and one smoke script.

STEPS
1. Delete app/integrations/google_workspace/gmail_next.py (263 LOC). Its only import is google_service_next.execute_google_api_call; nothing imports it.
2. Delete app/integrations/google_workspace/google_directory_next.py (638 LOC). Imports google_service_next at lines 12-13; consumed only by its own test and the smoke script.
3. Delete app/integrations/google_workspace/google_service_next.py (641 LOC) - the execute_google_api_call string-dispatcher plus the hand-rolled time.sleep retry loop (lines ~225 and ~280).
4. Delete app/tests/integrations/google_workspace/test_google_service_next.py (877 LOC) and test_google_directory_next.py (592 LOC).
5. Delete app/tests/smoke/google_smoke_test.py (312 LOC). Its module docstring states it exists solely to smoke-test google_service_next and google_directory_next; it imports google_directory_next at line 46 and monkeypatches execute_google_api_call. With both modules gone the script has no subject. It is skipped by default under pytest unless RUN_SMOKE_TESTS=1, so deleting it changes no CI signal.
6. Re-run the deletion check: grep -rn for the three module names across the repo (excluding backlog/ and tmp/) must return zero, and find app/integrations -name "*_next.py" must list only the three AWS files still owned by TASK-23.3.

WHAT THIS SLICE DOES NOT TOUCH
- integrations/google_workspace/google_service.py - the separate, non-_next execute_google_api_call and its get_google_api_command_parameters docstring scraper (line 238) with 16 live consumer files. Owned by TASK-25.1. Its test file test_google_service.py stays untouched.
- integrations/google_workspace/gmail.py - the non-_next Gmail module. Its deletion is TASK-25.1.1's scope.
- integrations/google_workspace/client.py - the canonical factory + classify_google_error shipped by TASK-22.4. Unchanged.

AC-TO-STEP-TO-TEST
- AC#1 (no google_service_next / google_directory_next / gmail_next anywhere) -> Steps 1-3, 6. Verified by the grep/find commands in Step 6 rather than by a test, since the criterion is the absence of files.
- AC#2 (_next execute_google_api_call gone, non-_next one untouched) -> Steps 3 and 6; the surviving app/tests/integrations/google_workspace/test_google_service.py continues to pass unchanged, proving the non-_next dispatcher was not disturbed.
- AC#3 (smoke test no longer imports a deleted module; test tree shrinks, no surviving test imports a deleted module) -> Steps 4-5, plus a full pytest collection run (pytest --collect-only) proving no ImportError.

TEST MATRIX
This slice adds no tests. Its verification is: (a) full pytest collection succeeds with no unresolved imports; (b) the existing Google integration suites that survive (test_google_service.py, test_google_directory.py, test_gmail.py, test_google_drive.py, test_google_docs.py, test_sheets.py, test_google_calendar.py, test_google_meet.py) stay green with zero edits; (c) infrastructure/directory tests (the TASK-22.4 canonical path) stay green, confirming the surviving Google surface is untouched; (d) mypy and ruff clean.

ASSUMPTIONS AND DOUBTS
- Assumes zero dynamic/string-based imports of the three modules. Verified: grep for the bare module names (not just import statements) returns only the sites listed above, and no importlib.import_module call in the repo references google_workspace. Re-run the bare-name grep before deleting, including app/bin and .github/workflows.
- Assumes deleting google_smoke_test.py outright is preferred over repointing it at the canonical factory. Rationale: it is a standalone dev script whose subject is being deleted, it is skipped in CI by default, and the canonical Google path already has real coverage via infrastructure/directory tests from TASK-22.4. FLAGGED FOR HUMAN REVIEW: if an equivalent manual smoke script against integrations/google_workspace/client.py is wanted, that is net-new capability and belongs in its own follow-up task, not here.
- Assumes no import-linter contract or client-usage tooling enumerates these paths. Check app/bin/generate_client_usage_matrix.sh and app/bin/baselines/ before merging - a shell script running under set -euo pipefail that takes a now-deleted path as a find argument will abort, which is the failure mode observed while planning TASK-22.5.

BLAST RADIUS AND ROLLBACK
Zero production blast radius: 1542 LOC of unreachable integration code and 1781 LOC of tests for it. A single git revert restores every file. No ordering constraint against TASK-23.2 or TASK-23.3 - this slice can merge before, after, or between them.

SIZE GATE: passes comfortably. Six file deletions, zero surviving-code edits, no new logic.
<!-- SECTION:PLAN:END -->
