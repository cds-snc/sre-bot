---
id: TASK-25.2.4.3
title: Migrate ops_group_assignment.py onto the Organizations and SSO-Admin adapters
status: To Do
assignee: []
created_date: '2026-09-14 17:39'
updated_date: '2026-09-15 12:50'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4.1
references:
  - app/modules/aws/ops_group_assignment.py
  - app/tests/unit/modules/aws/test_ops_group_assignment_handler.py
parent_task_id: TASK-25.2.4
priority: high
ordinal: 202000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2a of TASK-25.2.4. Minimal migration of modules/aws/ops_group_assignment.py (only production caller: modules/aws/groups.py:139, the admin-gated, help-text-hidden `/aws groups ops` Slack command) off the legacy integrations.aws.organizations and integrations.aws.sso_admin mirrors onto the adapters landed by TASK-25.2.4.1: build_organizations_adapter() and build_sso_admin_adapter() from packages/aws_platform/adapters/.

Call sites (read 2026-09-15):
- organizations.list_organization_accounts() (line 48): a False return crashes the list comprehension at lines 53-57 (TypeError, pinned by TASK-25.2.1).
- sso_admin.list_account_assignments_for_principal(principal_id, principal_type="GROUP") (line 49): a False return crashes the set comprehension at line 50. The legacy mirror also let ClientError propagate raw, and the adapter now wraps it.
- sso_admin.create_account_assignment(...) (line 85): does not crash. It branches on a truthy bool (line 91), so the failure reason is swallowed. The adapter returns OperationResult[bool], with data=False when the initial AWS status is FAILED (IN_PROGRESS counts as success, no polling; decided in TASK-25.2.4.1).

Reuse the caller-side idiom already in this file for build_identity_center_adapter().get_group_id (lines 23-45): an explicit non-success branch that logs status/error_code/error and returns a failed status carrying the adapter message.

Bugs in the touched file, fixed simply (human decision 2026-09-15): (a) the returned status reflects only the last account processed, so an earlier failure is reported as success; (b) if every unassigned account lacks an Id, `status` is never bound and execute() raises UnboundLocalError.

Feature is effectively unused (not called in 3+ weeks, no known user); no retry, polling, UX or groups.py changes. Reassessed when the business feature moves to packages/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/ops_group_assignment.py no longer imports integrations.aws.organizations or integrations.aws.sso_admin; list_organization_accounts, list_account_assignments_for_principal and create_account_assignment are called through build_organizations_adapter() / build_sso_admin_adapter() and branch on OperationResult explicitly
- [ ] #2 A non-success result from list_organization_accounts or list_account_assignments_for_principal makes execute() return a failed status carrying the adapter message and log status, error_code and error, with no assignment attempted; the two pinned TypeError crash tests in tests/unit/modules/aws/test_ops_group_assignment_handler.py are replaced by tests of this behaviour
- [ ] #3 A create_account_assignment result that is non-success, or successful with data False (initial AWS status FAILED), counts as a failed assignment: the reason is logged for that account and the remaining accounts are still processed
- [ ] #4 execute() returns a failed status naming every account whose assignment failed when at least one failed (no last-account-wins), and returns a failed status instead of raising UnboundLocalError when no unassigned active account has an Id
- [ ] #5 Per-call-site error-path behaviour (one line per call site) is recorded in the task notes for review
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUND TRUTH (read 2026-09-15): app/modules/aws/ops_group_assignment.py (113 LOC); its only production caller app/modules/aws/groups.py:126-157 (request_groups_ops, which handles the status values "success"/"failed"/"ok" and a falsy "disabled" response, needs no change); app/tests/unit/modules/aws/test_ops_group_assignment_handler.py (15 tests; groups routing covered separately by tests/unit/modules/aws/test_groups_command_handler.py:82-97, untouched); app/packages/aws_platform/adapters/organizations.py (list_organization_accounts -> OperationResult[list[dict]], :97) and sso_admin.py (list_account_assignments_for_principal -> OperationResult[list[dict]], :155, InstanceArn injected by _paginate :88; create_account_assignment -> OperationResult[bool], :106-129); closed plans/notes of TASK-25.2.4.1 and .2 and the TASK-25.2.4 coordinator notes.

ALIGNMENT WITH TASK-25.2.4.1/.2
- Use only the landed factories build_organizations_adapter() / build_sso_admin_adapter(): no providers.py registration and no adapter changes. The adapters already classify NOT_FOUND (incl. Organizations AccountNotFoundException/TargetNotFoundException added in .1), UNAUTHORIZED and TRANSIENT; unmapped ClientErrors and programmer errors propagate, as for get_group_id today.
- Build adapters inside execute(), never at import (eager AssumeRole), after the feature flag and group lookup short-circuits, so the disabled/group-failure paths build nothing.
- create_account_assignment keeps .1's semantics: initial status != FAILED is success, no polling.
- Standing TASK-25.2.4 decisions: fix bugs in touched files simply; legacy tests brought up to standard only within scope (file keeps its legacy name, which predates testing-standards; renaming would be a mechanical change mixed into a behaviour PR).

STEP 1 - tests first (red): app/tests/unit/modules/aws/test_ops_group_assignment_handler.py
- Mechanical re-stub of existing tests: replace @patch("modules.aws.ops_group_assignment.organizations"/"sso_admin") with @patch("...build_organizations_adapter"/"...build_sso_admin_adapter"). The adapter methods return OperationResult.success(data=[...]) for listings and OperationResult.success(data=True) for assignments. Assertions stay as they are, retargeted to mock_build_*.return_value.<method>. Group-failure tests additionally assert neither builder is called.
- Replace the two crash tests (see matrix) and add the new failure/bug-fix tests.

STEP 2 - app/modules/aws/ops_group_assignment.py
- Imports: drop `from integrations.aws import organizations, sso_admin`; add `from packages.aws_platform.adapters.organizations import build_organizations_adapter` and `from packages.aws_platform.adapters.sso_admin import build_sso_admin_adapter`.
- After aws_ops_group_id is resolved:
  accounts_result = build_organizations_adapter().list_organization_accounts()
  if not accounts_result.is_success: log.error("organization_accounts_lookup_failed", group_name, status=.status.value, error_code, error=.message); return {"status": "failed", "message": f"Failed to list AWS Organization accounts: {accounts_result.message}"}
  sso_admin_adapter = build_sso_admin_adapter()
  assignments_result = sso_admin_adapter.list_account_assignments_for_principal(principal_id=aws_ops_group_id, principal_type="GROUP")
  if not assignments_result.is_success: log.error("ops_group_account_assignments_lookup_failed", ...same fields); return {"status": "failed", "message": f"Failed to list account assignments for Ops group '{group_name}': {assignments_result.message}"}
  organizations_accounts = accounts_result.data or []; assigned_account_ids = {a["AccountId"] for a in assignments_result.data or []}
- The unassigned/"ok" branch stays unchanged.
- Loop (bug fixes a+b): before the loop, assigned: list[str] = [] and failed: list[str] = []. Keep the missing-Id log+continue. For each account:
  result = sso_admin_adapter.create_account_assignment(user_id=aws_ops_group_id, account_id=account_id, permission_set="write", principal_type="GROUP")
  label = account.get("Name") or account_id
  if result.is_success and result.data: append label to assigned; keep the "ops_group_assigned_to_account" info log.
  else: append label to failed; account_log.error("failed_to_assign_ops_group_to_account", group_name, status=result.status.value, error_code=result.error_code, error=result.message if not result.is_success else "assignment creation status FAILED").
- After the loop:
  if failed: return {"status": "failed", "message": f"Failed to assign Ops group '{group_name}' to {len(failed)} account(s): {', '.join(failed)}."} (a partial success still reports failed; successful accounts stay visible in the info logs).
  if assigned: return {"status": "success", "message": f"Ops group '{group_name}' assigned to {len(assigned)} account(s): {', '.join(assigned)}."}
  otherwise (every unassigned account lacked an Id): return {"status": "failed", "message": f"No Ops group assignment made: {len(unassigned_accounts)} unassigned active account(s) have no Id."}
- Minor tidy-up inside the same lines only: use the existing local group_name instead of repeated aws_feature_settings.AWS_OPS_GROUP_NAME in the rewritten messages. No other refactor.

TEST MATRIX (file: tests/unit/modules/aws/test_ops_group_assignment_handler.py; existing tests re-stubbed onto adapter mocks)
| Case | Test | AC |
|---|---|---|
| Feature disabled -> None, no builder called | test_should_return_none_when_feature_disabled (existing) | 1 |
| Group NOT_FOUND / other lookup failures / success without id -> failed, no org or sso adapter built | existing 3 tests, patch targets updated | 1 |
| Happy path, 2 unassigned -> success naming both, 2 create calls, list assignments called with principal_type GROUP | test_should_assign_group_to_unassigned_accounts (re-stubbed) | 1 |
| All assigned -> ok | test_should_return_ok_when_all_accounts_assigned (re-stubbed) | 1 |
| Suspended/closed skipped; mixed statuses; permission set "write"/GROUP args | existing 3 tests (re-stubbed) | 1 |
| list_organization_accounts non-success (parametrized TRANSIENT_ERROR, UNAUTHORIZED, NOT_FOUND) -> failed with adapter message, error log fields, no assignment listing or create | test_should_return_failed_when_list_organization_accounts_fails (replaces test_should_raise_when_list_organization_accounts_returns_false) | 2 |
| list_account_assignments_for_principal non-success -> failed with adapter message, error log, no create | test_should_return_failed_when_list_account_assignments_fails (replaces test_should_raise_when_list_account_assignments_returns_false) | 2 |
| create_account_assignment error result (TRANSIENT_ERROR) -> failed naming account, error logged with status/error_code/message | test_should_return_failed_when_assignment_fails (rewritten from the bool False version) | 3 |
| create_account_assignment success with data False -> failed, logged as creation status FAILED | test_should_return_failed_when_assignment_status_is_failed | 3 |
| Account A fails, account B succeeds -> failed naming only A, create called twice (continues) | test_should_report_failed_when_any_assignment_fails_and_continue | 3, 4 |
| Only unassigned account lacks Id -> failed status, no UnboundLocalError, create not called | test_should_return_failed_when_no_unassigned_account_has_id | 4 |
| Account without Id alongside one with Id -> success, 1 create call | test_should_handle_account_missing_id (re-stubbed) | 4 |

AC TRACEABILITY
- AC#1 <- Step 2 imports + adapter calls; re-stubbed happy-path tests (they patch only build_* factories, so any leftover mirror call would hit an unpatched module and fail the gates' import check; also verify with rg in the gate step)
- AC#2 <- Step 2 two listing branches; the two replacement tests
- AC#3 <- Step 2 loop else-branch; the assignment-failure tests
- AC#4 <- Step 2 post-loop aggregation; partial-failure and no-Id tests
- AC#5 <- implementation notes, using the lines below:
  * list_organization_accounts: any non-success (NOT_FOUND/UNAUTHORIZED/TRANSIENT) -> log organization_accounts_lookup_failed, return failed with adapter message, stop. Unmapped ClientError/programmer error propagates (the adapter contract).
  * list_account_assignments_for_principal: same, event ops_group_account_assignments_lookup_failed.
  * create_account_assignment: non-success or data False -> log failed_to_assign_ops_group_to_account with the reason, continue; the run returns failed naming those accounts.

VERIFICATION (from app/)
rg -n "integrations.aws import|integrations\.aws\.(organizations|sso_admin)" modules/aws/ops_group_assignment.py  (expect no output)
uv run ruff check .
uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
uv run pytest tests --ignore=tests/smoke
(Known pre-existing: 6 order-dependent SNS/google-directory failures in the single-process run; mypy errors outside touched files. Call out, don't fix.)

ASSUMPTIONS (each with how to verify)
- Same AWS role as today: both mirrors and both adapters resolve ORG_ROLE_ARN (SERVICE_ROLE_MAP "organizations"/"sso-admin" -> ORG_ROLE_ARN, integrations/aws/settings.py). Verify: rg -n "role_arn|SERVICE_ROLE_MAP" integrations/aws/organizations.py integrations/aws/sso_admin.py.
- No other production caller of ops_group_assignment.execute(). Verified 2026-09-15: rg finds only modules/aws/groups.py:139. Re-run before implementing.
- groups.py needs no change: every new return value uses the existing "failed"/"success"/"ok" keys it already renders.
- The legacy mirrors keep serving spending.py/aws_account_health.py until .4.7, so this slice does not touch them or their tests.

BLAST RADIUS AND ROLLBACK
- Only the admin-gated `/aws groups ops` Slack command, which has no known active user. Worst case: a wrong status message, or an assignment reported failed that AWS accepted (IN_PROGRESS semantics are unchanged from today).
- Adapter building performs eager AssumeRole: a role failure at build time raises, same as the existing build_identity_center_adapter() call at line 23. This pre-existing pattern is not a new risk.
- A single git revert restores the mirror-based behaviour. No settings, env, terraform or ordering constraints.

SIZE ESTIMATE AND GATE VERDICT
- Production: 1 file, about 45 changed LOC (imports 3, two listing branches about 20, loop/aggregation about 20). One subsystem. The behaviour change and bug fixes live in the same function and are not a separable mechanical refactor.
- Tests: 1 file (mechanical re-stub of 12 tests plus 5 new/replaced tests; not gated).
- VERDICT: well under the gate. One PR.

OPEN QUESTIONS FOR HUMAN REVIEW
None. Scope (minimal migration, not deletion) and both bug fixes were decided 2026-09-15.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Human decision 2026-09-14: keep ops_group_assignment migration to the bare minimum. The feature hasn't been called in at least 3 weeks and has no known active user; it will be reassessed when the business feature moves to packages/.
- create_account_assignment/delete_account_assignment keep the legacy behaviour: success is judged on the initial response Status != FAILED, with no polling of describe_account_assignment_creation_status/_deletion_status (IN_PROGRESS counts as success).
- Do only what AC#1-#3 require: swap to the adapters, add a simple explicit OperationResult branch with logging at the three call sites, and replace the pinned crash tests. No new retry, polling or UX logic.
- AC#3's per-status notes can be brief. One line per call site covering non-success (logged and handled like the existing get_group_id failure branch) is enough; there is no need to split NOT_FOUND/TRANSIENT/PERMANENT beyond what the existing pattern already does.

Planning 2026-09-15 (human decisions):
- Scope: minimal migration confirmed over deleting the `/aws groups ops` feature (option offered because the command is unused and absent from help text; declined).
- Bug fixes in the touched file: fix both (a) last-account-wins status and (b) UnboundLocalError when no unassigned account has an Id. ACs #3-#4 added for them; AC#2 reworded because only two call sites actually crashed on False (create_account_assignment swallowed the failure instead). The AC#3 per-status detail was simplified per the 2026-09-14 decision and is now AC#5.
<!-- SECTION:NOTES:END -->
