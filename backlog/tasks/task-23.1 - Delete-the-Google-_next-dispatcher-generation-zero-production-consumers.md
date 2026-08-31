---
id: TASK-23.1
title: Delete the Google _next dispatcher generation (zero production consumers)
status: Done
assignee: []
created_date: '2026-08-31 17:35'
updated_date: '2026-08-31 18:22'
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
- [x] #1 app/integrations/google_workspace contains no google_service_next.py, google_directory_next.py or gmail_next.py, and repo-wide grep for those three module names returns zero hits outside backlog/ and tmp/
- [x] #2 The _next-generation execute_google_api_call in google_service_next.py no longer exists; the separate non-_next execute_google_api_call in google_service.py is untouched (TASK-25.1 scope)
- [x] #3 app/tests/smoke/google_smoke_test.py is deleted and every reference to it is gone, including its RUN_SMOKE_TESTS opt-in flag; the tests/smoke directory, its smoke marker and the surviving AWS shield smoke test are unaffected
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 make test green; no production behavior change (deleted modules had zero production consumers)
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
5. Delete app/tests/smoke/google_smoke_test.py (312 LOC) outright (human-approved 2026-08-31). Its module docstring states it exists solely to smoke-test google_service_next and google_directory_next; it imports google_directory_next at line 46 and monkeypatches execute_google_api_call. Grep confirms the RUN_SMOKE_TESTS opt-in flag is referenced ONLY inside this file (lines 31, 37, 41), so the flag disappears with it and no Makefile target, workflow, or pyproject setting needs changing - pyproject's norecursedirs = ["tests/smoke"] and the smoke marker stay, since tests/smoke/integrations/aws/test_shield_smoke.py still lives there. No replacement smoke script is added; the canonical Google path is covered by the infrastructure/directory suites from TASK-22.4.
6. Prune the three deleted modules from app/bin/baselines/sdk_typing_antipatterns.txt so the SDK-typing freeze-baseline ratchets down (its header states removing entries is always safe; check_sdk_typing.py reports stale entries as INFO only).
7. Re-run the deletion checks: grep -rn for the three module names and for google_smoke_test / RUN_SMOKE_TESTS across the repo (excluding backlog/ and tmp/) must return zero; find app/integrations -name "*_next.py" must list only the three AWS files still owned by TASK-23.3; bin/check_sdk_typing.py, bin/check_deprecated_infra_client_imports.py and bin/generate_client_usage_matrix.sh must all pass.

WHAT THIS SLICE DOES NOT TOUCH
- integrations/google_workspace/google_service.py - the separate, non-_next execute_google_api_call and its get_google_api_command_parameters docstring scraper (line 238) with 16 live consumer files. Owned by TASK-25.1. Its test file test_google_service.py stays untouched.
- integrations/google_workspace/gmail.py - the non-_next Gmail module. Its deletion is TASK-25.1.1's scope.
- integrations/google_workspace/client.py - the canonical factory + classify_google_error shipped by TASK-22.4. Unchanged, and its existing test_client.py suite proves it survives.
- app/tests/smoke/ as a directory, its __init__.py files, the smoke pytest marker, and tests/smoke/integrations/aws/test_shield_smoke.py.

AC-TO-STEP-TO-TEST
- AC#1 (no google_service_next / google_directory_next / gmail_next anywhere) -> Steps 1-3, 6-7. Verified by the grep/find commands and by bin/check_sdk_typing.py, since the criterion is the absence of files rather than a runtime behavior.
- AC#2 (_next execute_google_api_call gone, non-_next one untouched) -> Steps 3 and 7; the surviving app/tests/integrations/google_workspace/test_google_service.py continues to pass unchanged, proving the non-_next dispatcher was not disturbed.
- AC#3 (smoke script and its references deleted) -> Step 5 plus the Step 7 grep.

TEST MATRIX
This slice adds no tests: nothing gains behavior, and the enduring guard against reintroducing a string-dispatch generation under app/integrations/ is bin/check_sdk_typing.py's freeze baseline, which already fails CI on net-new execute_*_api_call occurrences. Verification is therefore: (a) full pytest collection succeeds with no unresolved imports; (b) the surviving Google integration suites (test_google_service.py, test_google_directory.py, test_gmail.py, test_google_drive.py, test_google_docs.py, test_sheets.py, test_google_calendar.py, test_google_meet.py) and tests/unit/integrations/google_workspace/test_client.py stay green with zero edits; (c) infrastructure/directory tests (the TASK-22.4 canonical path) stay green; (d) mypy and ruff clean.

ASSUMPTIONS AND DOUBTS
- Assumes zero dynamic/string-based imports of the three modules. Verified: grep for the bare module names (not just import statements) returns only the sites listed above, and no importlib.import_module call in the repo references google_workspace. Re-run the bare-name grep before deleting, including app/bin and .github/workflows.
- RESOLVED (human, 2026-08-31): google_smoke_test.py is deleted outright rather than repointed at the canonical factory, and its references go with it. No follow-up smoke-script task is opened.
- RESOLVED (human, 2026-08-31): no absence-asserting unit test is kept. One was written first to drive the deletion, then removed once the modules were gone - check_sdk_typing.py already covers reintroduction, so a test asserting ModuleNotFoundError would only duplicate it.
- The client-usage/baseline tooling under app/bin DOES enumerate these paths (app/bin/baselines/sdk_typing_antipatterns.txt), hence Step 6. Also re-check app/bin/generate_client_usage_matrix.sh, which runs under set -euo pipefail and aborts if a find argument path disappears - the failure mode observed while planning TASK-22.5. It passes here because only files, not directories, are removed.

BLAST RADIUS AND ROLLBACK
Zero production blast radius: 1542 LOC of unreachable integration code and 1781 LOC of tests for it. A single git revert restores every file. No ordering constraint against TASK-23.2 or TASK-23.3 - this slice can merge before, after, or between them.

SIZE GATE: passes comfortably. Six file deletions plus a three-line baseline prune, zero surviving-code edits, no new logic.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Deleted (6 files, 3323 LOC):
- integrations/google_workspace/{google_service_next.py, google_directory_next.py, gmail_next.py}
- tests/integrations/google_workspace/{test_google_service_next.py, test_google_directory_next.py}
- tests/smoke/google_smoke_test.py

Changed: bin/baselines/sdk_typing_antipatterns.txt - removed the three deleted modules. This file was NOT in the original plan; it was found by re-running the bare-name grep, and it is exactly the "check app/bin/baselines before merging" doubt the plan flagged. Its own header states removing entries is always safe, and check_sdk_typing.py treats stale entries as INFO. Baseline now 22 entries (was 25).

Net test change: none. A temporary absence-asserting unit test (three parametrized ModuleNotFoundError assertions plus one canonical-module presence assertion) was written first to drive the deletion red-to-green, then removed on request once the modules were gone - bin/check_sdk_typing.py's freeze baseline already fails CI on any net-new execute_*_api_call occurrence under app/integrations/, so keeping the test would only duplicate that guard. tests/unit/integrations/google_workspace/test_client.py (the canonical factory/classifier suite) is untouched and still proves the surviving module.

Verification:
- grep for google_service_next / google_directory_next / gmail_next / google_smoke_test / RUN_SMOKE_TESTS across the repo returns zero hits outside backlog/ and tmp/. RUN_SMOKE_TESTS was referenced only inside the deleted smoke script, so no Makefile / workflow / pyproject change was needed; tests/smoke/ survives for test_shield_smoke.py.
- find integrations -name "*_next.py" now lists only the three AWS files (TASK-23.3 scope).
- bin/check_sdk_typing.py: OK. bin/check_deprecated_infra_client_imports.py: OK. bin/generate_client_usage_matrix.sh: exit 0.
- ruff: clean. mypy: 107 pre-existing errors in 40 files, none in google_workspace (unchanged by this slice).
- Tests, using the CI split from app/Makefile: test-new (tests/unit + tests/integration) and test-legacy (tests/api tests/modules tests/integrations tests/utils test_factory_validation.py) both green.

PRE-EXISTING FAILURES, NOT CAUSED BY THIS SLICE: running every directory in ONE pytest process (uv run pytest tests --ignore=tests/smoke) yields 5 failures - 2 in tests/integrations/aws/test_client_next.py (caplog does not capture structlog output depending on which tests ran first; that file is deleted by TASK-23.3) and 3 in tests/modules/webhooks/test_webhooks_aws_sns.py (the sns_message_validator mock does not apply, so the test attempts a real cert fetch). Proven independent of this change: pytest tests/integration tests/modules reproduces all three SNS failures while touching nothing this slice deleted, and test_client_next.py fails the same way when run entirely alone. Both pass under the Makefile's CI split. Worth a separate test-pollution task.
<!-- SECTION:NOTES:END -->
