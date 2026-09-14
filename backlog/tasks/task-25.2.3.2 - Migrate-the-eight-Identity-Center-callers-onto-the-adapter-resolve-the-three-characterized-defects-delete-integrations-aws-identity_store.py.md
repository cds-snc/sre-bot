---
id: TASK-25.2.3.2
title: >-
  Migrate the eight Identity Center callers onto the adapter, resolve the three
  characterized defects, delete integrations/aws/identity_store.py
status: To Do
assignee: []
created_date: '2026-09-11 19:18'
updated_date: '2026-09-11 21:11'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.3.1
references:
  - app/integrations/aws/identity_store.py
  - app/modules/aws/identity_center.py
  - app/modules/aws/aws.py
  - app/modules/aws/aws_access_requests.py
  - app/modules/aws/ops_group_assignment.py
  - app/modules/provisioning/users.py
  - app/modules/provisioning/groups.py
  - app/modules/provisioning/entities.py
  - app/jobs/revoke_aws_sso_access.py
  - app/jobs/scheduled_tasks.py
  - decisions/outbound-clients.md
parent_task_id: TASK-25.2.3
priority: high
ordinal: 193000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 (contract) of TASK-25.2.3, split 2026-09-11 under the single-PR size gate. Depends on TASK-25.2.3.1 (the adapter). Moves every production caller of integrations.aws.identity_store onto packages/aws_platform/adapters/identity_center.build_identity_center_adapter(), resolves the three defects the TASK-25.2.1 characterization pass pinned, deletes the legacy module and its 890-line test file, and prunes the two guard baselines.

Callers (re-grepped 2026-09-11; eight files, ten call sites): modules/aws/identity_center.py (list_users at :70/:79; create_user/delete_user/create_group_membership/delete_group_membership passed as callables to entities.provision_entities at :155/:171/:261/:282/:329/:348), modules/aws/aws.py (:158 inside request_aws_account_access, dead), modules/aws/aws_access_requests.py (:194 get_user_id), modules/aws/ops_group_assignment.py (:20 get_group_id), modules/provisioning/users.py (:58 list_users), modules/provisioning/groups.py (:142 list_groups_with_memberships), jobs/revoke_aws_sso_access.py (:30 get_user_id), jobs/scheduled_tasks.py (:128 healthcheck).

Human decisions 2026-09-11 on the error paths: bulk listings that fail raise the module-local DirectoryUsersUnavailableError / DirectoryGroupsUnavailableError (mirroring the Google branches) instead of crashing with TypeError; access_view_handler sends the existing "not registered with AWS SSO" reply on NOT_FOUND and falls to the existing "Failed to provision" reply on any other failure, never reaching already_has_access or create_account_assignment; the revoke job logs status/error_code, skips delete_account_assignment and expire_request for that request and continues (same outcome as today's exception path, made explicit); request_aws_account_access is deleted with its pinned tests; the healthcheck registration becomes lambda: build_identity_center_adapter().healthcheck().is_success. entities.provision_entities is not changed: it tests `if response:` and an OperationResult instance is always truthy, so modules/aws/identity_center.py wraps each adapter write in a small local bridge that maps the entity dict to adapter arguments and returns result.data on success or False (logged with status and error_code) on failure.

Test files to retarget (patch build_identity_center_adapter / a fake adapter instead of the legacy module): tests/unit/modules/aws/{test_identity_center_handler,test_aws_access_requests_handler,test_aws_command_handler,test_ops_group_assignment_handler}.py, tests/unit/modules/provisioning/test_provisioning_users.py, tests/modules/provisioning/test_provisioning_groups.py, tests/unit/jobs/test_revoke_aws_sso_access.py, tests/integration/jobs/{test_revoke_aws_sso_access_integration,test_scheduled_tasks_integration}.py. tests/integration/integrations/aws/test_identity_store_conformance.py is NOT orphaned: it exercises moto against packages/access's adapter and never imports the legacy module, so it stays untouched. packages/access is not reworked.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All four subtasks (TASK-25.2.3.2.1, TASK-25.2.3.2.2, TASK-25.2.3.2.3, TASK-25.2.3.2.4) are Done, with TASK-25.2.3.2.4 landing last; a repo-wide grep shows zero references to integrations.aws.identity_store and the module no longer exists
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
COORDINATOR TASK -- implementation lives in four subtasks, not here.

This task's original 10 ACs and full grounded plan (adapter contract, per-file call-site inventory, defect analysis, size-gate arithmetic) remain in this task's history as the scope record; the size gate on that plan came back "exceeds" (~587 production LOC, 11 files, mechanical-refactor + behavior-change + deletion mixed in one PR), so the human approved splitting it into four independently-planned, independently-shippable subtasks instead of executing it as one PR. See the 2026-09-11 comment for the size-gate numbers and subtask list.

Execution order (dependency-wired in the CLI, not just narrative):
1. TASK-25.2.3.2.1 (provisioning/users.py + groups.py listings) and TASK-25.2.3.2.2 (modules/aws/identity_center.py) and TASK-25.2.3.2.3 (access_view_handler, ops_group_assignment, revoke job) can proceed in any order or in parallel -- each depends only on TASK-25.2.3.1 (the adapter, already completed) and touches disjoint files.
2. TASK-25.2.3.2.4 (delete request_aws_account_access, flip the healthcheck lambda, delete integrations/aws/identity_store.py + its test, prune both guard baselines) depends on all three of the above and must land last, once no production caller of identity_store remains.

Each subtask carries its own full implementation plan, AC set, and test matrix scoped to what it alone touches. This task closes (human decision, not automated) once all four subtasks are Done -- at that point a repo-wide grep for integrations.aws.identity_store should return zero hits and the legacy module and its test file should no longer exist.

No production code, tests, or further decomposition happen directly on this task; its role from here is tracking only.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-11 20:09
---
2026-09-11 carried over from TASK-25.2.3.1 for the caller migration: classify_aws_error now maps ConflictException to PERMANENT_ERROR (app/integrations/aws/client.py), where it previously propagated as a raised ClientError. When migrating each call site, account for that at every write that can conflict: create_user and create_group_membership in modules/aws/identity_center.py's provision_entities bridge (an 'already exists' conflict must be recorded as a failed entity and the sync must continue, matching the legacy False-swallow rather than aborting), and any other classify_aws_error consumer touched by the migration. Also verify packages/access's ensure_user path still behaves acceptably now that a conflict arrives as a result instead of an exception (the access feature is not enabled; document, do not rework). The per-call-site error-path notes required by AC#1 must state explicitly how a PERMANENT_ERROR conflict is handled at each site.
---

created: 2026-09-11 20:56
---
2026-09-11: Per the size-gate verdict in this task's plan (approx. 587 production LOC across 11 files, mixing a mechanical import swap across 8 callers with 3 independent behavior fixes and a contract deletion -- exceeding the ~400 LOC / ~10 file / mechanical-vs-behavior-mix thresholds), this task is split into four subtasks, each independently shippable and reviewable:
- TASK-25.2.3.2.1 -- Migrate provisioning listings (users.py, groups.py) onto the Identity Center adapter
- TASK-25.2.3.2.2 -- Migrate modules/aws/identity_center.py onto the Identity Center adapter
- TASK-25.2.3.2.3 -- Fix the three AWS SSO error-path defects (access_view_handler, ops_group_assignment, revoke job)
- TASK-25.2.3.2.4 -- Delete dead request_aws_account_access, flip healthcheck lambda, delete integrations/aws/identity_store.py, prune guard baselines (depends on the three above; must land last)
This task (25.2.3.2) becomes the coordinator; its own ACs are left as-is below rather than retired, since only a human should decide whether to retire them in favour of "all four subtasks done." If that's the preferred framing, consider replacing ACs #1-#10 with a single "all four subtasks are Done" criterion, or leaving them as a scope record and closing this task once the subtasks close.
---

created: 2026-09-11 21:11
---
2026-09-11: human retired the ten original ACs; each is now carried by the subtask that owns it (listings → .1, identity_center.py → .2, the three error-path defects → .3, deletion/healthcheck/baselines/repo-wide grep → .4). The coordinator's single AC is 'all four subtasks Done'.
---
<!-- COMMENTS:END -->
