---
id: TASK-25.1.7
title: Delete the orphaned google_service.py dispatcher module
status: To Do
assignee: []
created_date: '2026-09-02 13:26'
updated_date: '2026-09-10 18:49'
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
- [ ] #1 integrations/google_workspace/google_service.py and tests/integrations/google_workspace/test_google_service.py are deleted; a repo-wide grep run from the repository root (excluding backlog/ and tmp/) for execute_google_api_call, get_google_api_command_parameters, handle_google_api_errors and get_google_service returns no hits outside: app/bin/check_sdk_typing.py (its own docstring and detection regex, which describe the anti-pattern by name), the header comment of app/bin/baselines/sdk_typing_antipatterns.txt (the per-file entry itself is removed by AC#2), and decisions/sdk-typing.md (any line; decision records are not edited by this task)
- [ ] #2 integrations/google_workspace/google_service.py is pruned from app/bin/baselines/sdk_typing_antipatterns.txt and python3 bin/check_sdk_typing.py passes
- [ ] #3 decisions/sdk-typing.md's Google-side Checks are verified green: no string-dispatch and no docstring-based parameter discovery remain anywhere in app/integrations/google_workspace/
- [ ] #4 ruff, mypy and pytest tests --ignore=tests/smoke are green with no behavior change; the hasattr assertion the task originally cited at tests/integrations/google_workspace/test_sheets.py:250 no longer applies because that file was already deleted under TASK-25.1.6.10.4 - confirm no equivalent stale assertion exists elsewhere in the suite
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (grep/read-verified on feat/add_ci_guardrail_vendor_package 2026-09-10; re-grep before deleting)
- app/integrations/google_workspace/ holds only __init__.py, client.py and google_service.py (273 LOC: get_google_service :42, handle_google_api_errors :80, execute_google_api_call :165, get_google_api_command_parameters :238). It re-exports GOOGLE_WORKSPACE_CUSTOMER_ID (:35), GCP_SRE_SERVICE_ACCOUNT_KEY_FILE (:36), SRE_BOT_EMAIL (:37), INCIDENT_TEMPLATE (:38), and imports convert_kwargs_to_camel_case from integrations.utils.api (:30).
- Zero importers repo-wide except app/tests/integrations/google_workspace/test_google_service.py (482 lines, the only file left in that test directory besides __pycache__; no __init__.py there).
- Repo-wide grep for execute_google_api_call|get_google_api_command_parameters|handle_google_api_errors|get_google_service hits only: the module, its test, bin/check_sdk_typing.py (docstring :13, detection regex :35 - the guardrail script's own anti-pattern description), bin/baselines/sdk_typing_antipatterns.txt (header comment :2 describing the baseline's purpose, plus the per-file entry :17 removed by AC#2), and decisions/sdk-typing.md (Context :17, Decision :28, Checks :45-46; visible only when the grep runs from the repository root). No hits in pyproject.toml, .github/, bin/generate_client_usage_matrix.sh, or any conftest. The "google_service" matches in tests/unit/infrastructure/{drive,directory}/test_factory.py and test_google.py are an unrelated fixture/local-variable name, not a reference to this module.
- Every re-exported constant already has its real consumers reading from infrastructure.configuration.integrations.google (get_google_workspace_settings/get_google_resources_config) or packages/incident/drive/adapters/google_drive.py::INCIDENT_TEMPLATE - confirmed by grepping each constant name outside the module and its test.
- convert_kwargs_to_camel_case (integrations/utils/api.py) loses its only production caller once this module is deleted; TASK-25.1.6.11.3 owns removing it. Not touched here.
- Dependency TASK-25.1.6.10 is status To Do, but subtasks .10.1-.10.5 are all Done and sheets.py/google_drive.py are already deleted from disk: the "zero production importers" precondition is satisfied in code (see task comment). This plan proceeds on that basis; it does not change .10's status.
- AC#1 and AC#4 were refreshed 2026-09-10 to drop stale wording (the old test_sheets.py:250 reference and an unachievable grep scope). AC#1 names the repository root as the grep location and allows any line of decisions/sdk-typing.md - see task comments.

STEP 1 - delete the module and its test
Pre-flight (re-run immediately before deleting, from the repository root): rg -n --hidden -g '!backlog/**' -g '!tmp/**' -g '!**/.venv/**' 'google_workspace[./]google_service\b|google_workspace import google_service\b' . -> expect only the two files below.
Delete app/integrations/google_workspace/google_service.py and app/tests/integrations/google_workspace/test_google_service.py. The now-empty tests/integrations/google_workspace/ directory (only __pycache__ remains) needs no further action - pytest and git do not track empty directories.

STEP 2 - prune the sdk-typing baseline
app/bin/baselines/sdk_typing_antipatterns.txt: delete the line integrations/google_workspace/google_service.py (:17). Leave the header comment and the ten AWS entries untouched - the AWS side is out of scope for this task.

STEP 3 - verify the ADR's Google-side Checks
No file edit. The pre-authored guards in app/tests/unit/integrations/google_workspace/test_google_workspace_package_sdk_call_shape.py parse every module under app/integrations/google_workspace/ and fail on any getattr with a non-literal attribute name or any __doc__ read. They currently fail on google_service.py:202/212/232/253 (getattr) and :257/259 (__doc__), and pass once Step 1 deletes the module - client.py already has neither shape. This closes decisions/sdk-typing.md's Checks for the Google vendor package specifically; the ADR's overall "migration complete" criterion is not reached because the AWS baseline entries remain (out of scope for this task).

STEP 4 - verification (each line names its working directory)
- AC#1, from the repository root: rg -n --hidden -g '!backlog/**' -g '!tmp/**' -g '!**/.venv/**' 'execute_google_api_call|get_google_api_command_parameters|handle_google_api_errors|get_google_service\b' . -> exactly app/bin/check_sdk_typing.py:13 and :35, app/bin/baselines/sdk_typing_antipatterns.txt:2 (header comment) and decisions/sdk-typing.md:17, :28, :45, :46. Running it from app/ would silently miss decisions/.
- AC#2, from app/: python3 bin/check_sdk_typing.py -> passes; uv run pytest tests/unit/bin/test_check_sdk_typing.py -> all pass, including test_sdk_typing_baseline_lists_no_google_workspace_files.
- AC#3, from app/: uv run pytest tests/unit/integrations/google_workspace/test_google_workspace_package_sdk_call_shape.py -> all pass.
- AC#4, from app/: uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' ; uv run pytest tests --ignore=tests/smoke.

AC TRACEABILITY
AC#1 -> Step 1; evidence: Step 4 grep plus a clean pytest collection (no dangling import).
AC#2 -> Step 2; evidence: Step 4 check_sdk_typing.py run and test_sdk_typing_baseline_lists_no_google_workspace_files passing.
AC#3 -> Steps 1 and 3; evidence: test_google_workspace_package_sdk_call_shape.py passing.
AC#4 -> Step 1 (removes the file the stale assertion pointed at); evidence: Step 4 ruff/mypy/pytest output.

TEST MATRIX
Failing tests already authored; keep them after this task lands (durable guards, not deletion scaffolding):
- app/tests/unit/integrations/google_workspace/test_google_workspace_package_sdk_call_shape.py: test_google_workspace_package_resolves_no_sdk_attribute_from_a_runtime_string and test_google_workspace_package_reads_no_sdk_docstring fail today on google_service.py; test_detectors_flag_retired_shapes_and_ignore_static_access_and_prose passes today and proves the guards cannot pass vacuously.
- app/tests/unit/bin/test_check_sdk_typing.py: test_sdk_typing_baseline_lists_no_google_workspace_files fails today on the google_service.py baseline entry.
Implementation must not edit these tests to make them pass. Regression proof also comes from existing suites:
- Full pytest collection catches any missed importer via ImportError at collection time.
- mypy catches any missed importer via unresolved-import error.
- bin/check_sdk_typing.py confirms the baseline no longer lists a file that doesn't exist and that no net-new anti-pattern hit appears.
Tests deleted: test_google_service.py in full (482 lines) - it covers only the deleted module's functions.

ASSUMPTIONS AND DOUBTS
(a) TASK-25.1.6.10's own status (To Do) does not block this deletion because its production prerequisite is already met in code (all five subtasks Done, sheets.py/google_drive.py gone) - flagged via comment for a human to reconcile the status, not silently overridden here.
(b) HUMAN DECISION (2026-09-10): no file under decisions/ is edited by this task. decisions/sdk-typing.md stays unchanged; its grep matches (:17, :28, :45, :46) are allowed by AC#1.
(c) get_google_api_command_parameters is a positional-only-ish helper with no type annotations (resource_obj, method) on its own signature - irrelevant post-deletion, noted only because it was the last untyped surface in the vendor package.
(d) No entry-point/plugin registration references google_service (confirmed no pyproject.toml hit) - safe to delete without touching plugin wiring.

BLAST RADIUS AND ROLLBACK
Runtime impact: none. No production importer of google_service.py exists anywhere in the repo today. A missed consumer would surface as an ImportError at pytest collection or a mypy unresolved-import error, both CI gates, before merge. A single git revert restores both files unchanged. No settings, env vars, terraform or CI pipeline changes. Independent of TASK-25.1.6.11.2 (CI guardrail) and TASK-25.1.6.11.3 (retire integrations/utils/api.py) - both are downstream and expect this deletion to have already landed; this task does not depend on either.

SIZE GATE
Production: 2 files deleted (google_service.py, 273 LOC) + 1 file trimmed by one line (sdk_typing_antipatterns.txt). Tests: 1 file deleted (482 LOC); the failing guards (1 new file, about 95 LOC, and one test added to test_check_sdk_typing.py) are already authored. One subsystem (Google Workspace vendor package), one change kind (deletion). Well inside the ~400 LOC / ~10 file / two-subsystem gate - no decomposition needed.
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

created: 2026-09-10 18:49
---
2026-09-10: Corrected the verification commands. AC#1's grep now runs from the repository root (from app/ it never searched decisions/) and allows the baseline header comment at sdk_typing_antipatterns.txt:2 and any line of decisions/sdk-typing.md (:17, :28, :45, :46). Step 4's AC#3 grep used an app/-prefixed path that fails from app/; AC#2 and AC#3 are now proven by the pre-authored failing tests listed in the TEST MATRIX, which stay after this task lands.
---
<!-- COMMENTS:END -->
