---
id: TASK-25.2.3.2.3
title: >-
  Migrate ops_group_assignment.py's get_group_id onto the Identity Center
  adapter with an explicit error path
status: Done
assignee: []
created_date: '2026-09-11 20:55'
updated_date: '2026-09-14 14:25'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.3.1
references:
  - app/modules/aws/ops_group_assignment.py
  - app/packages/aws_platform/adapters/identity_center.py
  - decisions/outbound-clients.md
  - app/modules/aws/groups.py
  - app/tests/unit/modules/aws/test_ops_group_assignment_handler.py
  - app/infrastructure/operations/result.py
parent_task_id: TASK-25.2.3.2
priority: high
ordinal: 196000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-25.2.3.2 (split 2026-09-11 under the single-PR size gate; re-scoped 2026-09-14). Migrates modules/aws/ops_group_assignment.py:20 -- the one remaining live identity_store lookup in this group, reached from /aws groups ops through modules/aws/groups.py:139 -- onto build_identity_center_adapter().get_group_id(). The caller branches explicitly on OperationResult instead of on a falsy sentinel.

Human decision carried over: NOT_FOUND keeps the existing 'not found' failed status; any other non-success returns a new failed status carrying result.message; the success path is unchanged. The organizations.list_organization_accounts and sso_admin.* calls in the same file stay on their legacy mirrors (TASK-25.2.4 owns them).

Re-scope 2026-09-14 (human decision): the original access_view_handler (modules/aws/aws_access_requests.py) and revoke-job (jobs/revoke_aws_sso_access.py) items are removed from this task. That access-request flow is not operational in production: /aws access is labelled "currently disabled", and the revoke job is scheduled nowhere and only processes rows that flow writes. packages/access will re-provide the capability. No code parity is kept for it: it is deleted under TASK-25.2.3.2.4 instead of fixed here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 ops_group_assignment.py uses build_identity_center_adapter().get_group_id(); NOT_FOUND keeps the existing 'not found' failed status, any other non-success returns a failed status carrying result.message (logged with status and error_code) without calling organizations or sso_admin, and the success path is unchanged
- [x] #2 test_ops_group_assignment_handler.py patches build_identity_center_adapter instead of identity_store in every test; the not-found case returns a NOT_FOUND OperationResult, and a new case covers a non-NOT_FOUND failure
- [x] #3 ops_group_assignment.py does not import integrations.aws.identity_store
- [x] #4 ruff, mypy (no new errors) and pytest pass with output recorded; a grep of ops_group_assignment.py shows zero references to identity_store
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (read 2026-09-14): app/modules/aws/ops_group_assignment.py (95 lines; lookup at :20, falsy guard + 'not found' status at :21-27, organizations/sso_admin calls from :29); app/modules/aws/groups.py:139-150 (the only caller: renders status 'failed' as "❌ *Error*: {message}", so a new failed message needs no caller change); app/packages/aws_platform/adapters/identity_center.py:163-173 (get_group_id calls GetGroupId via _call -> OperationResult[str]); app/integrations/aws/settings.py:56-63 (ResourceNotFoundException is in NOT_FOUND_CODES, so a missing group arrives as OperationStatus.NOT_FOUND); app/infrastructure/operations/result.py (success(data=...), error(status, message, error_code); message is str, never None); app/integrations/aws/identity_store.py:148 (legacy get_group_id -- the handle_aws_api_errors decorator returned False on any failure, so today every lookup failure, including throttling or AccessDenied, is reported as 'not found'); app/tests/unit/modules/aws/test_ops_group_assignment_handler.py (11 tests, 10 patching modules.aws.ops_group_assignment.identity_store).

## Findings
1. The defect is real and live. Because the legacy mirror collapses every failure to False, /aws groups ops tells an AWS admin "Ops group '...' not found" when the real cause is throttling, AccessDenied or a transient error. With OperationResult the two cases are finally distinguishable.
2. The existing not-found test stubs get_group_id -> None, but the legacy mirror never returned None. That is harmless today (both are falsy), and it is replaced by a real NOT_FOUND result.
3. Scope boundary: organizations.list_organization_accounts (:29) and sso_admin.* (:30, :66) stay on their legacy mirrors. TASK-25.2.4 owns them, and its pinned crash tests (:278, :308) keep patching those mirrors unchanged.
4. Import boundary: modules -> packages/aws_platform is the established precedent (modules/aws/identity_center.py, modules/provisioning/users.py); decisions/migration.md rule 2 forbids only the reverse direction.

## Ordered Steps (TDD)
### Step 1 -- failing tests (app/tests/unit/modules/aws/test_ops_group_assignment_handler.py)
- In the 10 tests that patch identity_store, swap `@patch("modules.aws.ops_group_assignment.identity_store")` for `@patch("modules.aws.ops_group_assignment.build_identity_center_adapter")` and rename the parameter `mock_build_adapter`. `get_group_id.return_value = "group-123"` becomes `mock_build_adapter.return_value.get_group_id.return_value = OperationResult.success(data="group-123")`. Import OperationResult and OperationStatus from infrastructure.operations, as test_provisioning_users.py already does.
- test_should_return_failed_when_group_not_found: return `OperationResult.error(OperationStatus.NOT_FOUND, message="Group not found", error_code="ResourceNotFoundException")`. Assert status 'failed', "not found" in message, get_group_id called once with "OpsGroup". Add organizations/sso_admin patches and assert neither is called.
- NEW test_should_return_failed_with_lookup_error_when_group_lookup_fails, parametrized over TRANSIENT_ERROR/ThrottlingException, UNAUTHORIZED/AccessDeniedException and PERMANENT_ERROR/ValidationException. Assert: status 'failed'; message contains the result message; "not found" not in message; organizations.list_organization_accounts and sso_admin.* are not called; the bound logger's error() is called with "ops_group_lookup_failed", status=<status>.value and error_code=<code>. Patch modules.aws.ops_group_assignment.logger and assert on `mock_logger.bind.return_value.error`.
- NEW test_should_return_failed_with_lookup_error_when_lookup_succeeds_without_group_id (boundary): success with data=None goes down the non-NOT_FOUND failure path instead of calling sso_admin with a None principal.
- Run and record red: expect AttributeError on the build_identity_center_adapter patch target.

### Step 2 -- implementation (app/modules/aws/ops_group_assignment.py)
- Imports: delete `identity_store` from the integrations.aws import (keep organizations, sso_admin); add `from infrastructure.operations import OperationStatus` and `from packages.aws_platform.adapters.identity_center import build_identity_center_adapter`.
- Replace :20-27 with the following (build the adapter at call time, never at import):
```
group_name = aws_feature_settings.AWS_OPS_GROUP_NAME
group_result = build_identity_center_adapter().get_group_id(group_name)
if group_result.status is OperationStatus.NOT_FOUND:
    log.error("ops_group_not_found", group_name=group_name)
    return {"status": "failed", "message": f"Ops group '{group_name}' not found in AWS Identity Center."}
if not group_result.is_success or not group_result.data:
    log.error("ops_group_lookup_failed", group_name=group_name, status=group_result.status.value, error_code=group_result.error_code, error=group_result.message)
    return {"status": "failed", "message": f"Failed to look up Ops group '{group_name}' in AWS Identity Center: {group_result.message}"}
aws_ops_group_id = group_result.data
```
- The NOT_FOUND message string and the 'ops_group_not_found' log event are byte-identical to today's. Nothing from :29 onward changes.

### Step 3 -- verification (from app/)
`uv run ruff check .`; `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` (compare against the 87-error / 31-file baseline recorded by TASK-25.2.3.2.1 and .2.2; zero new errors); `uv run pytest tests --ignore=tests/smoke` (the 6 known TASK-90 order leaks in test_webhooks_aws_sns.py / test_google.py are pre-existing; `make test` is the CI-shaped confirmation); `rg -n identity_store modules/aws/ops_group_assignment.py` expecting no hits. Record outputs in notes.

## AC Traceability
- AC#1 -> Step 2 -> the retargeted not-found test, the new parametrized lookup-failure test, the success-without-data boundary test, and the 8 unchanged-behaviour tests still green.
- AC#2 -> Step 1.
- AC#3 -> Step 2 imports -> the Step 3 grep.
- AC#4 -> Step 3.

## Test Matrix
- Happy path: success(data="group-123") -> the existing assign / ok / suspended / missing-Id / mixed / permission-set paths are unchanged.
- Not found: NOT_FOUND -> the legacy 'not found' failed status; no Organizations/SSO-Admin calls.
- Failure: TRANSIENT_ERROR, UNAUTHORIZED, PERMANENT_ERROR -> failed status carrying result.message, logged with status and error_code; no downstream calls. This is the behaviour change: previously reported as 'not found'.
- Boundary: success with data=None -> lookup-failed status; sso_admin is never called with a None principal.
- Unchanged pins: the list_organization_accounts / list_account_assignments False crash tests stay as-is (TASK-25.2.4).

## Risks
- result.message is the botocore error text, now shown in Slack. The audience is limited to AWS_ADMIN_GROUPS members (groups.py:134 permission gate), and AWS error messages carry no secrets. Accepted, per the carried-over human decision to include result.message.
- The mypy "no new errors" gate assumes ops_group_assignment.py currently contributes zero errors; confirm against the baseline run.

## Blast Radius and Rollback
One production file, one test file; only /aws groups ops is affected. A single git revert restores prior behaviour; identity_store.py still exists until TASK-25.2.3.2.4. Independent of .2.1/.2.2 (merged); must precede .2.4.

## Size Gate (PASSES)
1 production file, ~20 production LOC changed, 1 subsystem, a single behaviour change with no mechanical-refactor mix. Far under the ~400 LOC / ~10 file thresholds.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed and why:
- app/modules/aws/ops_group_assignment.py is the only production file touched. identity_store was dropped from the integrations.aws import (organizations and sso_admin stay, since TASK-25.2.4 owns them). Added imports for OperationStatus (infrastructure.operations) and build_identity_center_adapter.
- The lookup now calls build_identity_center_adapter().get_group_id(group_name) at call time and branches on the result:
  - NOT_FOUND: same 'not found' failed status and ops_group_not_found log as before, byte-identical.
  - Any other non-success, or a success with no data: a new failed status, "Failed to look up Ops group '<name>' in AWS Identity Center: <result.message>", logged as ops_group_lookup_failed with group_name, status, error_code and error. Returns before any Organizations or SSO Admin call.
  - Success: aws_ops_group_id = result.data, and everything downstream is unchanged.
- Behaviour change: throttling, AccessDenied and other non-NOT_FOUND failures used to be reported as 'not found', because the legacy mirror collapsed every error to False. They are now reported with their real cause. The only caller, modules/aws/groups.py:139, already renders any 'failed' status as an error reply, so it needed no change.
- No deviations from the plan.

Evidence (run from app/):
- uv run pytest tests/unit/modules/aws/test_ops_group_assignment_handler.py -> 15 passed (14 failed / 1 passed before the implementation).
- rg -n identity_store modules/aws/ops_group_assignment.py -> no hits.
- uv run ruff check . -> All checks passed. ruff format --check on both files -> already formatted.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 87 errors in 31 files (checked 355 source files). Same as the recorded baseline, with zero errors in modules/aws.
- uv run pytest tests --ignore=tests/smoke (single process) -> 6 failed, 3415 passed. The 6 are the known test-order state leaks tracked by TASK-90, unrelated to this change:
  - tests/modules/webhooks/test_webhooks_aws_sns.py: 3 failures.
  - tests/unit/infrastructure/directory/test_google.py: 3 failures.

Remaining for the human:
- Review and commit. The agent ran no git commands.
- Only a human moves the task to Done.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-14 14:05
---
2026-09-14 re-scope (human decision): AC#1 (access_view_handler) and AC#3 (revoke job) were removed, because that flow is dead in production and is deleted under TASK-25.2.3.2.4 with no code parity. The remaining ACs were narrowed to ops_group_assignment.py.
---

created: 2026-09-14 14:07
---
2026-09-14 planning: plan written for the re-scoped task (ops_group_assignment.py only). References now point at the ops call site and its caller instead of the deleted access-request flow. Awaiting human approval of the plan before implementation.
---

created: 2026-09-14 14:18
---
2026-09-14: failing tests written (TDD red) in app/tests/unit/modules/aws/test_ops_group_assignment_handler.py; no production code touched.

Evidence (from app/): uv run pytest tests/unit/modules/aws/test_ops_group_assignment_handler.py -q -> 14 failed, 1 passed. All 14 failures are the same error: AttributeError, modules.aws.ops_group_assignment has no attribute build_identity_center_adapter (the patch target). The 1 pass is test_should_return_none_when_feature_disabled, which never reaches the lookup. uv run ruff check -> All checks passed. ruff format --check -> already formatted.

Mapping to plan and ACs:
- AC#1 / AC#2, not-found: test_should_return_failed_when_group_not_found now returns a NOT_FOUND OperationResult (ResourceNotFoundException). It asserts the exact legacy message 'Ops group 'OpsGroup' not found in AWS Identity Center.', and that no organizations or sso_admin calls are made.
- AC#1 / AC#2, other failures: test_should_return_failed_with_lookup_error_when_group_lookup_fails, parametrized over TRANSIENT_ERROR/ThrottlingException, UNAUTHORIZED/AccessDeniedException and PERMANENT_ERROR/ValidationException. It asserts a failed status that carries result.message, never says 'not found', logs ops_group_lookup_failed once with group_name, status, error_code and error, and makes no downstream calls.
- AC#1 boundary: test_should_return_failed_when_group_lookup_succeeds_without_group_id. A success result with data=None gives a failed status that doesn't say 'not found', and sso_admin is never called.
- AC#1 success path unchanged: the 8 existing happy-path and pinned-crash tests are retargeted to OperationResult.success(data='group-123'). Two small regression guards were added: list_account_assignments_for_principal receives principal_id='group-123', and create_account_assignment receives user_id='group-123', so result.data (not the result object) is what flows downstream.
- AC#2: every identity_store patch was replaced by modules.aws.ops_group_assignment.build_identity_center_adapter.
- Unchanged: the two pinned organizations/sso_admin False-crash tests still patch the legacy mirrors (TASK-25.2.4 owns them).

ACs stay unchecked until implementation turns these tests green.
---

created: 2026-09-14 14:25
---
2026-09-14: the human ran make test (CI-shaped) and the full suite is green, which confirms the 6 single-process failures are only the TASK-90 test-order leaks. All 4 ACs were verified. The human reviewed the work and moved the task to Done.
---
<!-- COMMENTS:END -->
