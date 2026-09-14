---
id: TASK-25.2.3.2.4
title: >-
  Delete the dead AWS access-request flow and request_aws_account_access, flip
  healthcheck lambda, delete integrations/aws/identity_store.py, prune guard
  baselines
status: To Do
assignee: []
created_date: '2026-09-11 20:56'
updated_date: '2026-09-14 14:55'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.3.2.1
  - TASK-25.2.3.2.2
  - TASK-25.2.3.2.3
references:
  - app/modules/aws/aws.py
  - app/jobs/scheduled_tasks.py
  - app/integrations/aws/identity_store.py
  - app/bin/baselines/sdk_typing_antipatterns.txt
  - app/bin/baselines/vendor_package_contract.txt
  - decisions/outbound-clients.md
  - app/modules/aws/aws_access_requests.py
  - app/jobs/revoke_aws_sso_access.py
  - .devcontainer/dynamodb-create.sh
  - app/bin/seed.sh
  - app/bin/db.sh
parent_task_id: TASK-25.2.3.2
priority: high
ordinal: 197000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 (contract, final) of TASK-25.2.3.2 (split 2026-09-11 under the single-PR size gate; re-scoped 2026-09-14). Must land after slices 1-3, once no live production caller of integrations.aws.identity_store remains.

Human decisions carried over: request_aws_account_access is dead code (no production caller; confirmed by rg) and is deleted with its three pinned tests, along with the now-unused get_account_id_by_name import in modules/aws/aws.py; the scheduled_tasks.py 'aws' healthcheck registration becomes 'lambda: build_identity_center_adapter().healthcheck().is_success', mirroring the existing maxmind pattern at the same call site.

Re-scope 2026-09-14 (human decisions):
- The AWS account access-request flow is DELETED, not migrated, and no code parity is kept. It is not operational in production: /aws access is labelled "currently disabled", jobs/revoke_aws_sso_access.py is not registered in jobs/scheduled_tasks.py and only processes rows that flow writes, and packages/access will re-provide the capability. Removing a dead Slack command inside a frozen module is recorded as a bug-fix-shaped change under decisions/migration.md rule 1; there is no ADR amendment and no pre-deletion smoke test. The characterized defects in this flow (access_view_handler's unreachable 'is None' guard; the revoke job forwarding a failed lookup) are resolved by this deletion, not fixed.
- Production deletions: app/modules/aws/aws_access_requests.py and app/jobs/revoke_aws_sso_access.py. In app/modules/aws/aws.py: the 'Access to AWS accounts' docstring line (:4), the aws_access_requests import (:20), the '(currently disabled)' /aws access help-text lines (:48-51), bot.view("aws_access_view") (:64) and the `case "access":` branch (:102-103). A typed `/aws access` then falls to the existing 'Unknown command' reply. With request_aws_account_access also gone, aws.py imports nothing from integrations.aws and drops out of TASK-25.2.4's caller list.
- Test deletions: tests/unit/modules/aws/test_aws_access_requests_handler.py; tests/unit/jobs/test_revoke_aws_sso_access.py; tests/integration/jobs/test_revoke_aws_sso_access_integration.py; test_should_open_access_modal_when_access_command_given in test_aws_command_handler.py (:64); test_modules_aws_access_requests_dynamodb_endpoint_matrix and its aws_access_requests import in tests/unit/integrations/aws/test_dynamodb_local_endpoint.py. The docstrings in test_aws_command_registration.py that say register() calls bot.view() twice (aws_access_view, aws_health_view) are corrected to the single aws_health_view registration.
- Local-dev table cleanup: the aws_access_requests block in .devcontainer/dynamodb-create.sh (:42-59); seed_aws_request (:138-184), its aws-request usage/example lines (:24-26, :35-36) and its `aws-request)` case branch (~:201) in app/bin/seed.sh; the aws_access_requests example line in app/bin/db.sh (:27).
- Out of scope: terraform/dynamodb.tf (aws_access_requests_table and its entry in the aws_backup_selection resources) and terraform/iam.tf:51. A separate follow-up task that depends on this one owns them, so data retention and backup recovery points can be checked before the prod table is destroyed. README.md:21 ("Manage AWS access requests and approvals") describes the capability packages/access delivers and stays. The organizations/sso_admin mirrors are not deleted here: ops_group_assignment, spending and aws_account_health still use them (TASK-25.2.4).
- Size gate: the human knowingly overrode it on 2026-09-14. Roughly 820 production lines are deleted across ~6 app files plus 3 shell scripts, together with ~1,300+ test lines. They stay in one PR because every change is dead-code removal or the one-line healthcheck flip; no live behaviour changes beyond that flip.

Then integrations/aws/identity_store.py and tests/integrations/aws/test_identity_store.py (890 lines) are deleted outright, and the identity_store lines are removed from bin/baselines/sdk_typing_antipatterns.txt and bin/baselines/vendor_package_contract.txt. tests/integration/integrations/aws/test_identity_store_conformance.py exercises packages/access's own adapter via moto and never imports the legacy module -- it stays untouched, as does packages/access.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/aws.py no longer defines request_aws_account_access, imports get_account_id_by_name, integrations.aws.identity_store or aws_access_requests, registers aws_access_view, routes an 'access' action, or lists /aws access in its help text; the three pinned request_aws_account_access tests and the access-modal routing test in test_aws_command_handler.py are deleted
- [ ] #2 modules/aws/aws_access_requests.py, jobs/revoke_aws_sso_access.py, test_aws_access_requests_handler.py, test_revoke_aws_sso_access.py and test_revoke_aws_sso_access_integration.py are deleted, as is the aws_access_requests case in test_dynamodb_local_endpoint.py; a grep of app/ for aws_access_requests, revoke_aws_sso_access and aws_access_view returns zero hits
- [ ] #3 The local aws_access_requests table is gone from .devcontainer/dynamodb-create.sh, app/bin/seed.sh (seed_aws_request plus its usage and case entries) and app/bin/db.sh, and bash -n passes on all three; terraform/ is untouched
- [ ] #4 jobs/scheduled_tasks.py's 'aws' healthcheck entry is 'lambda: build_identity_center_adapter().healthcheck().is_success', and no longer imports integrations.aws.identity_store; the integration test in test_scheduled_tasks_integration.py is retargeted to patch build_identity_center_adapter
- [ ] #5 integrations/aws/identity_store.py and tests/integrations/aws/test_identity_store.py are deleted; the identity_store lines are removed from bin/baselines/sdk_typing_antipatterns.txt and bin/baselines/vendor_package_contract.txt; test_identity_store_conformance.py and packages/access are untouched
- [ ] #6 ruff, mypy (no new errors), pytest, make check-sdk-typing and make check-vendor-package-contract pass with output recorded; a repo-wide grep shows zero references to integrations.aws.identity_store anywhere in app/
- [ ] #7 jobs/scheduled_tasks.py's integration_healthchecks treats an exception raised by any healthcheck callable as unhealthy: it logs integration_healthcheck_result result=unhealthy with the integration key and the error, and continues with the remaining checks
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (re-verified 2026-09-14 against main @ edeffb51; task line refs still accurate)
- app/modules/aws/aws.py (169 lines): docstring :4; imports :16 identity_store, :17 get_account_id_by_name, :20 aws_access_requests; help text :48-51 (blank separator, '(currently disabled)', /aws access, its description); bot.view("aws_access_view") :64; case "access" :102-103; request_aws_account_access :130-168. request_aws_account_access has no production caller (rg: only 3 tests).
- app/modules/aws/aws_access_requests.py 330 lines (imports identity_store/organizations/sso_admin; builds a boto3 dynamodb client at import time :24). app/jobs/revoke_aws_sso_access.py 50 lines, not registered in scheduled_tasks.py. app/integrations/aws/identity_store.py 379 lines; nothing in integrations/aws imports it.
- app/jobs/scheduled_tasks.py: :13 `from integrations.aws import identity_store`; :121-140 integration_healthchecks with dict[str, Callable[[], bool]], 'aws': identity_store.healthcheck at :128; maxmind lambda precedent :126; job wrapped by safe_run (:65, :98).
- packages/aws_platform/adapters/identity_center.py: build_identity_center_adapter() :296 (per-call construction, the precedent in slices 1-3 and the documented usage at :9); healthcheck() :102 -> OperationResult[bool] via _call, which classifies ClientError/BotoCoreError only. get_aws_client (integrations/aws/client.py:138-187) does eager AssumeRole when a role ARN is mapped, and classify_aws_error re-raises unknown ClientError codes, so construction or unknown-code failures raise. The legacy check (identity_store.py:29-45) caught every Exception and returned False.
- Guard baselines: sdk_typing_antipatterns.txt:11 'integrations/aws/identity_store.py'; vendor_package_contract.txt:12 'module:integrations/aws/identity_store.py'. Both checkers only report stale entries as INFO and never fail on them, so pruning is hygiene and a net-new violation still fails. No other baseline, pyproject, CI workflow, locale, docs or decisions file references aws_access_requests, revoke_aws_sso_access, aws_access_view or the legacy identity_store. No alert or dashboard reads integration_healthcheck_result / safe_run_error (repo-wide rg).
- Tests: test_aws_command_handler.py (343 lines): access-modal test :62-~80, three request_aws_account_access tests :237-343. test_aws_command_registration.py docstrings :7-9 and :34-37 mention two bot.view calls. test_dynamodb_local_endpoint.py: import :10, matrix test :44-~100 (SimpleNamespace, importlib, pytest stay used by the remaining test). test_scheduled_tasks_integration.py: two tests patch jobs.scheduled_tasks.identity_store (:87-~130 all-healthy, :130-~165 partial failures). Whole-file deletions: test_aws_access_requests_handler.py (398), tests/unit/jobs/test_revoke_aws_sso_access.py (272), tests/integration/jobs/test_revoke_aws_sso_access_integration.py (192), tests/integrations/aws/test_identity_store.py (890). test_identity_store_conformance.py does not import the legacy module and stays.
- Shell: .devcontainer/dynamodb-create.sh :42-60 (block + trailing blank); app/bin/seed.sh usage :24-26, examples :35-36, Notes line :39 ('timestamps for AWS requests'), seed_aws_request :138-184 (+ blank), case branch :200-203; app/bin/db.sh :27. bash -n passes on all three today.
- ADRs: decisions/migration.md rule 1 (freeze; bug fixes allowed) covers removing a dead command in a frozen module. decisions/outbound-clients.md:33 (adapter is the boundary, returns OperationResult) is satisfied by the flip. No ADR discrepancy found; per-call adapter construction is not contradicted by outbound-clients.md (it prescribes factories, not provider singletons, for Path B adapters).

## Findings / decisions carried into the plan
1. Healthcheck failure semantics (HUMAN DECISION 2026-09-14, new AC#7): guard the integration_healthchecks loop with a per-entry try/except Exception, treated as unhealthy. The 'aws' entry stays the carried-over lambda. This keeps an aws failure visible as integration_healthcheck_result unhealthy (as legacy did) instead of a generic safe_run_error, and hardens the other three entries the same way.
2. Minor behaviour note (accepted, no action): legacy healthy = bool(list_users()), so an empty identity store read as unhealthy. The adapter treats an empty store as healthy. Production has users, so this has no practical effect.
3. After aws.py stops importing it, integrations/aws/organizations.get_account_id_by_name has no production caller. TASK-25.2.4 already owns dropping it with the organizations mirror, so it is not touched here.
4. Removing aws_access_requests also removes an import-time boto3 client construction when modules.aws.aws is imported, a small startup side-effect removal.

## Ordered Steps (TDD where behaviour exists)
### Step 1 -- failing tests (red)
a. tests/integration/jobs/test_scheduled_tasks_integration.py: in both healthcheck tests replace @patch("jobs.scheduled_tasks.identity_store") with @patch("jobs.scheduled_tasks.build_identity_center_adapter") (param mock_build_adapter); stub mock_build_adapter.return_value.healthcheck.return_value = OperationResult.success(data=True) (all-healthy) and an OperationResult.error/permanent_error (partial failures, now asserting the aws unhealthy log too); assert healthcheck call_count == 1. NEW test_healthcheck_logs_unhealthy_and_continues_when_a_check_raises: incident_drive healthcheck raises RuntimeError and build_identity_center_adapter raises (simulating a failed AssumeRole ClientError); assert integration_healthcheck_result result=unhealthy is logged for google_drive and aws with the error text, and maxmind/opsgenie are still called.
b. tests/unit/modules/aws/test_aws_command_handler.py: delete test_should_open_access_modal_when_access_command_given and the three request_aws_account_access tests. NEW test_should_reply_unknown_command_when_access_command_given (access now falls to 'Unknown command'), plus assert "/aws access" not in aws.help_text and hasattr(aws, "request_aws_account_access") is False.
c. tests/unit/modules/aws/test_aws_command_registration.py: correct both docstrings to the single aws_health_view registration; add bot.view.assert_called_once_with("aws_health_view").
d. Run and record red: expect AttributeError on the build_identity_center_adapter patch target, the unknown-command/help/hasattr assertions failing, and view called twice.

### Step 2 -- production: scheduled_tasks.py (AC#4, AC#7)
- Drop `from integrations.aws import identity_store`; add `from packages.aws_platform.adapters.identity_center import build_identity_center_adapter` (modules/jobs -> packages is the established direction; migration.md rule 2 forbids only the reverse).
- 'aws': lambda: build_identity_center_adapter().healthcheck().is_success
- Loop: `try: healthy = healthcheck()` / `except Exception as exc: healthy = False; error = str(exc)`, then the existing unhealthy log gains error=... when present (logger.error("integration_healthcheck_result", module=..., integration=key, result="unhealthy", error=...)). The healthy branch is unchanged. ~8 LOC.

### Step 3 -- production: aws.py (AC#1)
Delete docstring line :4, imports :16, :17 and aws_access_requests from the :19-26 tuple, help lines :48-51 (the help text then ends after the /aws health entry and its trailing '\n'), bot.view aws_access_view :64, case "access" :102-103, request_aws_account_access :130-168 (including its preceding blank lines). aws.py then imports nothing from integrations.aws.

### Step 4 -- delete the dead flow (AC#2)
Delete app/modules/aws/aws_access_requests.py, app/jobs/revoke_aws_sso_access.py, tests/unit/modules/aws/test_aws_access_requests_handler.py, tests/unit/jobs/test_revoke_aws_sso_access.py, tests/integration/jobs/test_revoke_aws_sso_access_integration.py. In tests/unit/integrations/aws/test_dynamodb_local_endpoint.py delete the :10 import and the test_modules_aws_access_requests_dynamodb_endpoint_matrix test (ruff confirms no leftover unused imports).

### Step 5 -- local-dev scripts (AC#3)
dynamodb-create.sh: remove the aws_access_requests block. seed.sh: remove the aws-request usage entry, the example pair, seed_aws_request, and the aws-request) case branch; reword the Notes line to 'All IDs are auto-generated (UUIDs)'. db.sh: replace the example with `$0 get sre_bot_access_requests ...` only if its key shape is confirmed from dynamodb-create.sh, otherwise just delete the line. Run bash -n on all three. terraform/ untouched (TASK-91).

### Step 6 -- delete legacy identity_store (AC#5)
Delete app/integrations/aws/identity_store.py and tests/integrations/aws/test_identity_store.py; remove sdk_typing_antipatterns.txt:11 and vendor_package_contract.txt:12. test_identity_store_conformance.py and packages/access untouched.

### Step 7 -- verification (AC#6), from app/
- uv run ruff check . ; uv run ruff format --check on touched .py files
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' : zero new errors vs the 87-error / 31-file baseline (the count may drop with deleted files)
- uv run pytest tests --ignore=tests/smoke : the 6 known TASK-90 order leaks (test_webhooks_aws_sns.py x3, test_google.py x3) are pre-existing; `make test` is the CI-shaped confirmation
- make check-sdk-typing ; make check-vendor-package-contract (expect OK with no stale INFO for identity_store)
- rg -n "integrations.aws.identity_store|integrations.aws import .*identity_store|aws_access_requests|revoke_aws_sso_access|aws_access_view|request_aws_account_access" app/ -> zero hits outside .venv
- bash -n ../.devcontainer/dynamodb-create.sh bin/seed.sh bin/db.sh ; git-free check that terraform/ is unchanged (rg shows the same 3 aws_access_requests hits as before)

## AC Traceability
- AC#1 -> Step 3 -> Step 1b/1c tests (unknown-command for access, help text, hasattr, single view registration).
- AC#2 -> Step 4 -> Step 7 rg.
- AC#3 -> Step 5 -> bash -n + terraform rg.
- AC#4 -> Step 2 -> Step 1a retargeted tests.
- AC#5 -> Step 6 -> guard make targets + rg.
- AC#6 -> Step 7.
- AC#7 -> Step 2 loop guard -> Step 1a new raising-check test.

## Test Matrix
- Happy: all four healthchecks succeed -> no error logs (retargeted all-healthy test).
- Failure (result): adapter healthcheck returns non-success -> aws unhealthy logged (partial-failures test).
- Failure (exception): a healthcheck callable raises or the adapter factory raises -> unhealthy logged with error, remaining checks still run (new test).
- Boundary: `/aws access` -> 'Unknown command' reply; `/aws help` no longer lists it; register() registers exactly one view.
- Removal: rg zero hits; guards OK; shell syntax OK.

## Assumptions / doubts (verify during implementation)
- The job-level safe_run tests (TestSchedulerErrorRecovery) are unaffected by the loop guard: they wrap arbitrary callables, not integration_healthchecks. Verify by running the file.
- No test imports modules.aws.aws_access_requests indirectly beyond the files listed: verify with rg after Step 4, before running the suite.
- The mypy baseline has no errors in scheduled_tasks.py: confirm by running mypy on the file before and after.

## Blast radius and rollback
Live behaviour changes: (1) the aws healthcheck now goes through the adapter every 5 minutes (two clients built per run, as in slices 1-3); (2) any raising healthcheck now logs unhealthy instead of aborting the job; (3) `/aws access`, already labelled disabled and not operational, now replies 'Unknown command'. No data or terraform changes; the prod aws_access_requests table is untouched (TASK-91). A single git revert restores everything. Ordering: slices .1-.3 are merged, so no live caller of identity_store remains; TASK-91 depends on this task.

## Size gate (HUMAN OVERRIDE 2026-09-14, recorded)
~10 production files (5 .py: 3 deleted, 2 edited; 2 baselines; 3 shell), ~870 production LOC removed, ~+10 LOC added (scheduled_tasks loop guard + import); ~1,850 test lines removed, ~+60 added. Exceeds ~400 LOC, but the human knowingly kept it as one PR because all of it is dead-code deletion plus the healthcheck flip and loop guard.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-14 14:08
---
2026-09-14 re-scope (human decisions): this task now also deletes the whole dead AWS access-request flow (aws_access_requests.py, /aws access, jobs/revoke_aws_sso_access.py) with no code parity, plus its local-dev table setup. That flow is not operational in production, and packages/access re-provides the capability. The work was placed here rather than in a new subtask by explicit human choice, overriding the ~400 production LOC size gate because all of it is dead-code removal. Terraform (dynamodb.tf table and backup selection, iam.tf:51) is excluded and moves to a separate follow-up task that depends on this one. ACs rewritten: new #1-#3 cover aws.py, the dead flow and the local scripts; the old #2-#4 become #4-#6 unchanged. Needs a fresh /plan-task pass before implementation.
---

created: 2026-09-14 14:38
---
2026-09-14 planning (human decision): the flipped aws healthcheck can raise outside OperationResult. Eager AssumeRole in get_aws_client, and classify_aws_error re-raising unknown codes, both escape the lambda, where legacy identity_store.healthcheck caught every Exception. Human chose to guard the integration_healthchecks loop with a per-entry try/except, treated as unhealthy, rather than a literal one-liner or an AWS-only helper. Added as AC#7. The 'aws' entry stays the carried-over lambda.
---

created: 2026-09-14 14:55
---
2026-09-14 planning follow-up (no scope change): the empty-store semantics difference (legacy bool(list_users()) vs adapter 'empty store is healthy') and the future of the log-only integration_healthchecks job are owned by TASK-92 (service health model decision). This task keeps the planned flip and loop guard; TASK-92 may later retire or replace the job.
---
<!-- COMMENTS:END -->
