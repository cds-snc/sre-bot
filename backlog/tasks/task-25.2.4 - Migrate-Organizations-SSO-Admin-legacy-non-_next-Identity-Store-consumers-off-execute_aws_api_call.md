---
id: TASK-25.2.4
title: >-
  Build the Organizations, SSO-Admin, Config, Cost Explorer, GuardDuty, Security
  Hub and Lambda adapters and migrate their callers; delete the seven mirrors
status: Done
assignee: []
created_date: '2026-07-31 18:49'
updated_date: '2026-09-15 19:55'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.3
references:
  - app/integrations/aws/organizations.py
  - app/integrations/aws/sso_admin.py
  - app/integrations/aws/config.py
  - app/integrations/aws/cost_explorer.py
  - app/integrations/aws/guard_duty.py
  - app/integrations/aws/security_hub.py
  - app/integrations/aws/lambdas.py
  - app/integrations/aws/client.py
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
parent_task_id: TASK-25.2
priority: high
ordinal: 121000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-25.2. Create packages/aws_platform/adapters/{organizations,sso_admin,config,cost_explorer,guard_duty,security_hub,lambda}.py following the shape proven by TASK-25.2.3: typed client from get_aws_client (with the AUDIT/ORG/LOGGING/SSO role ARNs from settings where the mirror uses them today), SDK paginators, try/except + classify_aws_error, OperationResult returns, Stubber unit tests. Organizations' small helpers travel with the adapter only if they still have a caller: get_account_id_by_name's only caller was request_aws_account_access, which TASK-25.2.3.2.4 deletes, so re-grep and drop it if unused. SSO-Admin's create/delete account-assignment status checks travel too; create_account_assignment is evaluated for the retries-disabled option.

Callers migrated (starting list, re-grep before planning): modules/aws/ops_group_assignment.py, modules/aws/spending.py, modules/aws/aws_account_health.py, modules/aws/lambdas.py. Error-path behaviour is documented per call site. Removed from this list on 2026-09-14 (human decision): modules/aws/aws_access_requests.py and jobs/revoke_aws_sso_access.py, the dead AWS account access-request flow, which TASK-25.2.3.2.4 deletes with no code parity (packages/access re-provides the capability); and modules/aws/aws.py, whose only integrations.aws use (get_account_id_by_name inside request_aws_account_access) is deleted by the same task.

Deleted with their last caller: integrations/aws/{organizations,sso_admin,config,cost_explorer,guard_duty,security_hub,lambdas}.py and tests/integrations/aws/test_{organizations,sso_admin,legacy_config,cost_explorer,guard_duty,security_hub,lambas}.py.

Size gate: seven small adapters (about 400 production LOC) plus four caller files sit at the single-PR limit. The planner splits this into an Organizations + SSO-Admin subtask and an account-health + Lambda subtask if the plan exceeds it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The seven adapters exist under packages/aws_platform/adapters/, return OperationResult, build clients only through get_aws_client, and have Stubber unit tests
- [x] #2 The listed caller files no longer import any of the seven mirrors and handle OperationResult explicitly, with error-path behaviour recorded in notes and reviewed
- [x] #3 The seven mirror modules and their legacy tests are deleted and both guard baselines pruned accordingly
- [x] #4 Every caller that today crashes on a False return from organizations, cost_explorer, config, guard_duty, security_hub or lambdas (dict/list comprehensions and len() over the result in aws_account_health, spending, ops_group_assignment and lambdas, as pinned by TASK-25.2.1) handles the non-success OperationResult status explicitly with a user-visible or logged outcome; the pinned crash tests are replaced by tests of the new behaviour
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
COORDINATOR PLAN. TASK-25.2.4 is decomposed into 7 subtasks under the single-PR size gate; this task's own ACs are satisfied by the union of its children. Ground truth verified 2026-09-14 by reading TASK-25.2's coordinator description, TASK-25.2.3's plan/notes and the landed code at app/packages/aws_platform/adapters/identity_center.py, app/integrations/aws/client.py and app/integrations/aws/settings.py.

WHY DECOMPOSED (size-gate evidence)
- The seven legacy mirrors total ~489 production LOC (organizations.py 96, sso_admin.py 145, config.py 45, cost_explorer.py 42, guard_duty.py 71, security_hub.py 32, lambdas.py 58); the identity_center adapter that set the pattern is 306 LOC for 13 operations (~23 LOC/op) across just one service. Seven adapters at a similar per-operation cost, plus four caller-file migrations (ops_group_assignment.py 113, spending.py 225, aws_account_health.py 247, lambdas.py 78 = 663 LOC of caller code touched) plus deleting 489 LOC of mirrors and ~419 LOC of legacy tests (test_organizations.py 424 down to ~419 total across the seven test files) is far over the ~400 production LOC / ~10 file gate in one PR, and mixes new adapter code (additive) with caller behaviour changes (the False-to-OperationResult contract change) and mechanical deletion -- three things the gate says must not ship in one PR.
- The task's own description anticipated a 2-way split (Organizations+SSO-Admin vs account-health+Lambda); re-grepping the actual callers shows organizations is shared by three callers (ops_group_assignment.py, spending.py, aws_account_health.py) and cost_explorer by two (spending.py, aws_account_health.py), so a clean per-adapter-pair split of the callers isn't possible without forcing spending.py or aws_account_health.py to depend on adapters from "the other half". The decomposition below instead follows expand/contract: build all adapters first (2 slices, split only by production-LOC balance), then migrate each caller file independently (4 slices, matching TASK-25.2.3's per-caller subtask shape), then delete the mirrors once every caller is off them (1 slice, matching TASK-25.2.3.2.4's precedent of bundling a deletion+baseline-prune as one subtask).

SUBTASKS AND DEPENDENCY ORDER
1. TASK-25.2.4.1 (expand) -- Build packages/aws_platform/adapters/organizations.py and sso_admin.py + Stubber tests. No caller changes. ~220 LOC, 2 production files.
2. TASK-25.2.4.2 (expand) -- Build packages/aws_platform/adapters/{config,cost_explorer,guard_duty,security_hub,lambda}.py + Stubber tests, plus the securityhub SERVICE_ROLE_MAP fix in integrations/aws/settings.py. No caller changes. ~260 LOC, 5 production files (+ 1-line settings.py fix).
3. TASK-25.2.4.3 (migrate, depends on .1) -- ops_group_assignment.py onto organizations + sso_admin.
4. TASK-25.2.4.4 (migrate, depends on .1, .2) -- spending.py onto organizations + cost_explorer.
5. TASK-25.2.4.5 (migrate, depends on .1, .2) -- aws_account_health.py onto organizations, cost_explorer, config, guard_duty, security_hub (largest single-file slice: 5 adapters, 6 call sites, one file).
6. TASK-25.2.4.6 (migrate, depends on .2) -- lambdas.py onto the lambda adapter.
7. TASK-25.2.4.7 (contract, depends on .3, .4, .5, .6) -- delete the seven mirrors + seven legacy test files, prune both guard baselines. Pure mechanical deletion once re-grep confirms zero remaining callers; kept as one bundled slice per the TASK-25.2.3.2.4 precedent (equivalent-shaped bundled deletion accepted there) despite ~16 files touched, since every file is a straight deletion or a baseline-line removal with no new logic to review.

Each slice keeps main green and is independently revertible: slices 1-2 are additive (unused code, zero risk to ship alone); slices 3-6 each touch exactly one caller file and can be reverted with a single git revert without breaking the other callers (the mirrors they stop calling are still present and correct until slice 7); slice 7 only runs after re-confirming no caller remains.

PATTERN REUSED FROM TASK-25.2.3 (verbatim, not reinvented)
- Client construction: get_aws_client(service_name, role_arn=..., retries=...) from app/integrations/aws/client.py (Literal-overloaded factory already supports organizations, sso-admin, ce, config, guardduty, securityhub, lambda -- confirmed in client.py's AwsServiceName Literal, no client.py changes needed).
- Adapter shape: a class holding the typed client(s), a private _call()/_paginate() helper wrapping try/except (ClientError, BotoCoreError) + classify_aws_error(exc) -> OperationResult.error(...), success calls returning OperationResult.success(data=...), and a module-level build_<name>_adapter() factory reading get_aws_settings().SERVICE_ROLE_MAP for the role ARN -- mirrors identity_center.py:46-54 (init), :68-82 (_call/_map_sdk_exception), :86-98 (_paginate), :296-306 (build_identity_center_adapter). No app/infrastructure/<service>/ Protocol and no packages/aws_platform/providers.py registry: packages/aws_platform is the documented provisional seam (TASK-25.2 description, TIER RULES section) and its own adapters already skip infrastructure/services/providers.py in favour of an inline build_*() factory -- this is a pre-approved, already-established deviation from the general "resolve infrastructure via singleton providers" rule, not a new one introduced here.
- Caller-side OperationResult branching: modules/aws/ops_group_assignment.py:23-45 already does this for the Identity Center adapter (build_identity_center_adapter().get_group_id(), OperationStatus.NOT_FOUND special-cased from other failures, then is_success/data/message/error_code) -- every migrate slice (.4.3-.4.6) reuses this exact caller-side idiom rather than inventing a new one.
- Test shape: one botocore.stub.Stubber-based test module per adapter (or per operation group) under app/tests/unit/packages/aws_platform/, named test_aws_platform_<service>_operations.py (matching test_aws_platform_identity_center_operations.py / _groups_join.py / _provider.py); one class per operation with a success test, a pagination test where relevant, and one test per mapped error family, plus an unmapped-exception-propagates test.
- Deletion shape: TASK-25.2.3.2.4 deleted integrations/aws/identity_store.py + its legacy test + pruned both guard baselines as one subtask after all callers were migrated -- TASK-25.2.4.7 repeats that shape for all seven mirrors at once.

DEAD CODE DROPPED, NOT PORTED (re-grepped 2026-09-14, verify again at implementation time)
- organizations.get_account_id_by_name (organizations.py:34) and get_active_account_names (organizations.py:22): zero production callers. get_account_id_by_name's only caller (request_aws_account_access) was deleted by TASK-25.2.3.2.4; get_active_account_names has no caller at all, not even internally.
- sso_admin.list_accounts_for_provisioned_permission_set (sso_admin.py:122): zero production callers found.
- lambdas.get_layer_version (lambdas.py:39): zero production callers found (modules/aws/lambdas.py only calls list_functions/list_layers).
Each build subtask's AC requires a re-grep confirmation before dropping, so a newly-discovered caller (e.g. in a script or job not covered by this grep pass) blocks the drop rather than silently losing behaviour.

AC TRACEABILITY (TASK-25.2.4's own ACs, satisfied by children)
- AC#1 (seven adapters + Stubber tests) <- .4.1, .4.2
- AC#2 (callers migrated, OperationResult explicit, error-path documented) <- .4.3, .4.4, .4.5, .4.6
- AC#3 (mirrors + legacy tests deleted, both baselines pruned) <- .4.7
- AC#4 (crash-on-False call sites now handle non-success explicitly, pinned crash tests replaced) <- .4.3 (3 sites), .4.4 (4 sites), .4.5 (6 sites), .4.6 (2 sites) -- 15 crash-on-False sites total, enumerated with file:line in each child's description

VERIFICATION (run in every child PR, from app/)
cd app && uv run ruff check .
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
cd app && uv run pytest tests --ignore=tests/smoke

BLAST RADIUS AND ROLLBACK
- Slices .4.1/.4.2 (new adapters, unused): zero production risk, trivially revertible.
- Slices .4.3-.4.6 (one caller file each): a git revert restores the exact prior mirror-based behaviour for that caller with no cross-file coupling, since the mirrors stay in place until .4.7. The behaviour change itself (False-swallow -> explicit OperationResult) is the intended, human-decided contract change from TASK-25.2 (AC-level "error contract" decision, 2026-09-11); each child's notes must record the concrete before/after per call site for human review, per that decision.
- Slice .4.7 (deletion): only runs once re-grep confirms zero remaining references; a revert restores the seven mirror files and tests exactly, with no adapter-side coupling since the adapters are additive and independent of the mirrors.
- Known pre-existing risk, not introduced or fixed by this task: TASK-25.2's comments #2/#3 document that eager AssumeRole (from TASK-25.2.2) can make app startup perform a real sts.assume_role when AWS_ORG_ACCOUNT_ROLE_ARN and ACCESS_SYNC_ENABLED are both set, which is a test-isolation gap tracked against TASK-25.2, not this task's adapters.

OPEN QUESTIONS FOR HUMAN REVIEW
- .4.5 (aws_account_health.py): the Slack health-check modal has no existing "partial failure" UI -- the plan proposes a per-field fallback string (e.g. "unknown") plus a log entry rather than failing the whole modal; confirm this is the desired UX rather than, e.g., showing an explicit error banner in the modal.
- .4.4 (spending.py): confirm whether a single AWS-account's spend/detail lookup failing during generate_spending_data should skip that account (partial report) or abort the whole run -- current crash-on-False behaviour aborts the whole run today, which the plan is not required to preserve given the AC#4 error-contract change, but the choice needs an explicit human decision recorded in that subtask's notes.
- Confirm the misspelled legacy test filename tests/integrations/aws/test_lambas.py (not test_lambdas.py) is intentional/historical and just needs deleting, not a sign a differently-named file also exists and was missed.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Human decisions 2026-09-14 (apply to every TASK-25.2.4.x subtask):
1. TEST TOOL: every AWS adapter test in this series uses botocore.stub.Stubber, matching TASK-25.2.3. This is a deliberate standard, not ADR compliance: decisions/testing.md:24 names moto for boto3 adapter tests, but moto is only installed as moto[dynamodb], nothing in app/tests uses it, and TASK-50 tracks the adoption. Keeping every adapter on the same tool makes a later switch to moto one uniform mechanical change.
2. BUG FIXES: fix any bug found in a file the subtask already touches, keeping the fix simple (modules/aws/ features will be rearchitected when they move to packages/). If a fix would push the subtask well past the single-PR size gate, stop and ask the human before splitting or deferring.
3. LEGACY TESTS: tests that predate decisions/testing.md are brought up to it only as far as the subtask's scope allows. Tests slated for deletion in .7 are not rewritten; the behaviour they pin is carried into the new adapter tests instead.

Close-out 2026-09-15 (from TASK-25.2.4.7): all seven children are implemented, so the coordinator ACs are checked. The status is left for a human.
- AC#1 (seven adapters with Stubber tests) <- TASK-25.2.4.1 (organizations, sso_admin) and TASK-25.2.4.2 (config, cost_explorer, guard_duty, security_hub, aws_lambda).
- AC#2 (callers on OperationResult, error paths recorded) <- TASK-25.2.4.3 ops_group_assignment, .4.4 spending, .4.5 aws_account_health, .4.6 lambdas. Per-call-site notes are on each child.
- AC#3 (mirrors and legacy tests deleted, baselines pruned) <- TASK-25.2.4.7.
- AC#4 (crash-on-False sites handled, pinned crash tests replaced) <- .4.3-.4.6 (.4.6 recorded that lambdas.py never crashed and fixed its failure/empty conflation instead).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-11 16:19
---
2026-09-11: TASK-25.2.1's characterization pass pinned several crash-on-False paths in this slice's callers (TypeError from comprehensions and len() over a bool). They are listed here so the migration replaces each with explicit status handling. The dead request_aws_account_access in modules/aws/aws.py is owned by TASK-25.2.3.
---

created: 2026-09-14 14:08
---
2026-09-14 (human decision): modules/aws/aws_access_requests.py and jobs/revoke_aws_sso_access.py were removed from the caller list and from AC#4. That access-request flow is dead in production and is deleted under TASK-25.2.3.2.4 with no code parity. modules/aws/aws.py was also removed: after that task it imports nothing from integrations.aws. AC#2 now says 'the listed caller files' instead of 'seven', and the size-gate line counts four caller files.
---

created: 2026-09-14 15:27
---
2026-09-14 (after TASK-25.2.3 closed): re-grep for the description's get_account_id_by_name note. Its only production caller (request_aws_account_access in modules/aws/aws.py) was deleted by TASK-25.2.3.2.4. rg across app/ now finds only the definition (integrations/aws/organizations.py:34) and its four legacy tests (tests/integrations/aws/test_organizations.py:383-423), so drop it with the organizations mirror; do not port it into the adapter. Also: comment #1's line saying request_aws_account_access is owned by TASK-25.2.3 is resolved (deleted). modules/aws/aws.py imports nothing from integrations.aws, and the identity_store dependency is gone (the TASK-25.2.3 dependency is now Done).
---
<!-- COMMENTS:END -->
