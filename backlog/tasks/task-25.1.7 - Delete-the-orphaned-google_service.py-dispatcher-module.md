---
id: TASK-25.1.7
title: Delete the orphaned google_service.py dispatcher module
status: To Do
assignee: []
created_date: '2026-09-02 13:26'
updated_date: '2026-09-10 18:37'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.1.6.10
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/google_service.py
parent_task_id: TASK-25.1
priority: medium
ordinal: 130000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Delete the now-orphaned legacy Google dispatcher module integrations/google_workspace/google_service.py and its test file tests/integrations/google_workspace/test_google_service.py (482 lines).

OWNERSHIP GAP THIS TASK CLOSES (found 2026-09-02 while planning TASK-25.1.5): no existing task owned this deletion. TASK-23 shipped Done with AC#3 explicitly scoping itself to the _next generation and deferring the non-_next execute_google_api_call plus the get_google_api_command_parameters docstring scraper to TASK-25.1. TASK-25.1's own AC#1 in turn says google_service.py is "slated for TASK-23 deletion" - now stale and circular. TASK-25.1.6 covers the shared execute helpers in client.py, not this module.

PRECONDITION: TASK-25.1.5 lands. At that point google_service.py has zero production importers repo-wide (grep-verified 2026-09-02: google_drive.py is the last one; the only other matches are bin/check_sdk_typing.py's own detection regex and a hasattr assertion in tests/integrations/google_workspace/test_sheets.py:250).

Scope: pure deletion. Delete the module and its test file; prune "integrations/google_workspace/google_service.py" from app/bin/baselines/sdk_typing_antipatterns.txt; confirm decisions/sdk-typing.md's Checks now pass for the Google vendor package (no execute_google_api_call, no getattr string-dispatch, no __doc__-based parameter discovery). Callers of the module's re-exported constants (INCIDENT_TEMPLATE, SRE_BOT_EMAIL, GOOGLE_WORKSPACE_CUSTOMER_ID) must already read them from infrastructure.configuration.integrations.google - TASK-25.1.5 does this for google_drive.py.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/google_workspace/google_service.py and tests/integrations/google_workspace/test_google_service.py are deleted; a repo-wide grep for execute_google_api_call, get_google_api_command_parameters, handle_google_api_errors and get_google_service returns no hits outside: bin/check_sdk_typing.py (its own docstring and detection regex, which describe the anti-pattern by name), bin/baselines/sdk_typing_antipatterns.txt's header comment (the per-file entry itself is removed by AC#2), and decisions/sdk-typing.md (the historical Context narrative and the Checks section, which both describe the anti-pattern rather than referencing this module)
- [ ] #2 integrations/google_workspace/google_service.py is pruned from app/bin/baselines/sdk_typing_antipatterns.txt and python3 bin/check_sdk_typing.py passes
- [ ] #3 decisions/sdk-typing.md's Google-side Checks are verified green: no string-dispatch and no docstring-based parameter discovery remain anywhere in app/integrations/google_workspace/
- [ ] #4 ruff, mypy and pytest tests --ignore=tests/smoke are green with no behavior change; the hasattr assertion the task originally cited at tests/integrations/google_workspace/test_sheets.py:250 no longer applies because that file was already deleted under TASK-25.1.6.10.4 - confirm no equivalent stale assertion exists elsewhere in the suite
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (grep/read-verified on feat/add_ci_guardrail_vendor_package 2026-09-10; re-grep before deleting)
- app/integrations/google_workspace/ holds only __init__.py, client.py and google_service.py (273 LOC: get_google_service :42, handle_google_api_errors :80, execute_google_api_call :165, get_google_api_command_parameters :238). It re-exports GOOGLE_WORKSPACE_CUSTOMER_ID (:35), GCP_SRE_SERVICE_ACCOUNT_KEY_FILE (:36), SRE_BOT_EMAIL (:37), INCIDENT_TEMPLATE (:38), and imports convert_kwargs_to_camel_case from integrations.utils.api (:30).
- Zero importers repo-wide except app/tests/integrations/google_workspace/test_google_service.py (482 lines, the only file left in that test directory besides __pycache__; no __init__.py there).
- Repo-wide grep for execute_google_api_call|get_google_api_command_parameters|handle_google_api_errors|get_google_service hits only: the module, its test, bin/check_sdk_typing.py (docstring :13, detection regex :35 - the guardrail script's own anti-pattern description), bin/baselines/sdk_typing_antipatterns.txt (header comment :2-3 describing the baseline's purpose, plus the per-file entry :17 removed by AC#2), and decisions/sdk-typing.md (Context :17, a historical narrative of the anti-pattern; Checks :45-46, the grep instructions themselves). No hits in pyproject.toml, .github/, bin/generate_client_usage_matrix.sh, or any conftest. The "google_service" matches in tests/unit/infrastructure/{drive,directory}/test_factory.py and test_google.py are an unrelated fixture/local-variable name, not a reference to this module.
- Every re-exported constant already has its real consumers reading from infrastructure.configuration.integrations.google (get_google_workspace_settings/get_google_resources_config) or packages/incident/drive/adapters/google_drive.py::INCIDENT_TEMPLATE - confirmed by grepping each constant name outside the module and its test.
- convert_kwargs_to_camel_case (integrations/utils/api.py) loses its only production caller once this module is deleted; TASK-25.1.6.11.3 owns removing it. Not touched here.
- Dependency TASK-25.1.6.10 is status To Do, but subtasks .10.1-.10.5 are all Done and sheets.py/google_drive.py are already deleted from disk: the "zero production importers" precondition is satisfied in code (see task comment). This plan proceeds on that basis; it does not change .10's status.
- AC#1 and AC#4 were refreshed this session to drop stale wording (the old test_sheets.py:250 reference and an achievable grep scope) - see task comments.

STEP 1 - delete the module and its test
Pre-flight (re-run immediately before deleting): rg -n --hidden -g '!backlog/**' -g '!tmp/**' -g '!**/.venv/**' 'google_workspace[./]google_service\b|google_workspace import google_service\b' . -> expect only the two files below.
Delete app/integrations/google_workspace/google_service.py and app/tests/integrations/google_workspace/test_google_service.py. The now-empty tests/integrations/google_workspace/ directory (only __pycache__ remains) needs no further action - pytest and git do not track empty directories.

STEP 2 - prune the sdk-typing baseline
app/bin/baselines/sdk_typing_antipatterns.txt: delete the line integrations/google_workspace/google_service.py (:17). Leave the header comment and the ten AWS entries untouched - the AWS side is out of scope for this task.

STEP 3 - verify the ADR's Google-side Checks
No file edit. Confirm by inspection that app/integrations/google_workspace/ (now __init__.py and client.py only) contains no getattr-based string dispatch and no __doc__ parsing - client.py already has neither (it holds only get_admin_directory_service/get_drive_service-style factories and classify_google_error, per TASK-25.1.6.11.1). This closes decisions/sdk-typing.md's Checks for the Google vendor package specifically; the ADR's overall "migration complete" criterion is not reached because the AWS baseline entries remain (out of scope - see ASSUMPTIONS).

STEP 4 - verification (from app/)
- AC#1: rg -n --hidden -g '!backlog/**' -g '!tmp/**' -g '!**/.venv/**' 'execute_google_api_call|get_google_api_command_parameters|handle_google_api_errors|get_google_service\b' . -> only bin/check_sdk_typing.py and decisions/sdk-typing.md remain.
- AC#2: python3 bin/check_sdk_typing.py -> passes; grep bin/baselines/sdk_typing_antipatterns.txt for google_workspace -> zero hits.
- AC#3: visual confirmation per Step 3; rg 'getattr\(|__doc__' app/integrations/google_workspace/ -> zero hits.
- AC#4: uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' ; uv run pytest tests --ignore=tests/smoke.

AC TRACEABILITY
AC#1 -> Step 1; evidence: Step 4 grep plus a clean pytest collection (no dangling import).
AC#2 -> Step 2; evidence: Step 4 check_sdk_typing.py run and baseline grep.
AC#3 -> Step 3; evidence: Step 4 getattr/__doc__ grep.
AC#4 -> Step 1 (removes the file the stale assertion pointed at); evidence: Step 4 ruff/mypy/pytest output.

TEST MATRIX
No new tests: pure deletion of code with zero production consumers and one now-orphaned test file for the deleted module. Regression proof comes from existing suites:
- Full pytest collection catches any missed importer via ImportError at collection time.
- mypy catches any missed importer via unresolved-import error.
- bin/check_sdk_typing.py confirms the baseline no longer lists a file that doesn't exist and that no net-new anti-pattern hit appears.
Tests deleted: test_google_service.py in full (482 lines) - it covers only the deleted module's functions.

ASSUMPTIONS AND DOUBTS
(a) TASK-25.1.6.10's own status (To Do) does not block this deletion because its production prerequisite is already met in code (all five subtasks Done, sheets.py/google_drive.py gone) - flagged via comment for a human to reconcile the status, not silently overridden here.
(b) decisions/sdk-typing.md line 17 (Context) and lines 45-46 (Checks) are left unedited by this plan: they describe the anti-pattern generically (needed for AWS's still-open entries) rather than naming this module specifically, so they are not "stale" in the same sense as the task's own AC#4 wording was. Recommend leaving Context as-is permanently (it is accurate history of why the ADR exists) and, at most, adding one short dated sentence to the existing "Changes:" log noting the Google-side Checks are satisfied once this task lands - but only once AWS's baseline is also empty, since the ADR's Checks section covers both vendors together and a partial-vendor edit could read as declaring the whole migration done prematurely. This is a judgment call on the ADR itself, not on this task's code - flagging for human decision rather than making the edit.
(c) get_google_api_command_parameters is a positional-only-ish helper with no type annotations (resource_obj, method) on its own signature - irrelevant post-deletion, noted only because it was the last untyped surface in the vendor package.
(d) No entry-point/plugin registration references google_service (confirmed no pyproject.toml hit) - safe to delete without touching plugin wiring.

BLAST RADIUS AND ROLLBACK
Runtime impact: none. No production importer of google_service.py exists anywhere in the repo today. A missed consumer would surface as an ImportError at pytest collection or a mypy unresolved-import error, both CI gates, before merge. A single git revert restores both files unchanged. No settings, env vars, terraform or CI pipeline changes. Independent of TASK-25.1.6.11.2 (CI guardrail) and TASK-25.1.6.11.3 (retire integrations/utils/api.py) - both are downstream and expect this deletion to have already landed; this task does not depend on either.

SIZE GATE
Production: 2 files deleted (google_service.py, 273 LOC) + 1 file trimmed by one line (sdk_typing_antipatterns.txt). Tests: 1 file deleted (482 LOC). One subsystem (Google Workspace vendor package), one change kind (deletion). Well inside the ~400 LOC / ~10 file / two-subsystem gate - no decomposition needed.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-08 14:37
---
ORDERING UPDATE (2026-09-08): dispatcher deletion is the penultimate destructive step, after every legacy Google surface migration (.6.6-.6.10) has landed. It remains pure deletion, but delaying it keeps rollback and final package verification straightforward.
---

created: 2026-09-10 18:34
---
2026-09-10: Refreshed AC#1's grep exclusion list and AC#4's stale test_sheets.py:250 / "make test" wording - both were written 2026-09-02 before sibling TASK-25.1.6.x work landed. Dependency TASK-25.1.6.10 is still status To Do, but all five of its subtasks (.10.1-.10.5) are Done and sheets.py/google_drive.py are deleted from disk - this task's precondition (zero production importers of google_service.py) is satisfied in code; only a human can move .10 to Done. Implementation plan added; no status change.
---

created: 2026-09-10 18:37
---
HUMAN DECISION (2026-09-10): do not edit any file under decisions/ in this task. decisions/sdk-typing.md stays unchanged; ASSUMPTIONS (b)'s optional dated sentence is out of scope. AC#1's decisions/sdk-typing.md grep hits remain allowed as-is.
---
<!-- COMMENTS:END -->
