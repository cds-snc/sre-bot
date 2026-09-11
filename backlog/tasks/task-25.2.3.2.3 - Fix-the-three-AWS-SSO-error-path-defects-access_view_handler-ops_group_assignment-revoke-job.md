---
id: TASK-25.2.3.2.3
title: >-
  Fix the three AWS SSO error-path defects (access_view_handler,
  ops_group_assignment, revoke job)
status: To Do
assignee: []
created_date: '2026-09-11 20:55'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.3.1
references:
  - app/modules/aws/aws_access_requests.py
  - app/modules/aws/ops_group_assignment.py
  - app/jobs/revoke_aws_sso_access.py
  - app/packages/aws_platform/adapters/identity_center.py
  - decisions/outbound-clients.md
parent_task_id: TASK-25.2.3.2
priority: high
ordinal: 196000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-25.2.3.2 (split 2026-09-11 under the single-PR size gate). Migrates the three remaining identity_store.get_user_id / get_group_id call sites (grouped because each is the same 'branch explicitly on OperationResult instead of a falsy sentinel' shape) and resolves the three characterized defects the TASK-25.2.1 characterization pass pinned. Human decisions carried over: (1) aws_access_requests.py's access_view_handler (:194) sends the existing 'not registered with AWS SSO' reply on a NOT_FOUND get_user_id, and falls to the existing 'Failed to provision' reply on any other non-success; already_has_access and create_account_assignment are not called on either failure path (replaces the dead 'is None' check, since the legacy integration actually returned False, never None). (2) ops_group_assignment.py (:20) keeps its existing 'not found' failed status on NOT_FOUND, and returns a new failed status carrying the result message on any other non-success; the success path is unchanged. (3) jobs/revoke_aws_sso_access.py (:30) logs status and error_code on a non-success get_user_id, skips delete_account_assignment and expire_request for that request, and continues to the next request in the loop -- the same outcome as today's exception path, made explicit rather than accidental.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 aws_access_requests.py's access_view_handler uses build_identity_center_adapter().get_user_id(); NOT_FOUND sends the existing 'not registered' reply, any other non-success sends the existing 'Failed to provision' reply, and already_has_access/create_account_assignment are called only on success; the two pinned dead-branch tests in test_aws_access_requests_handler.py are replaced
- [ ] #2 ops_group_assignment.py uses build_identity_center_adapter().get_group_id(); NOT_FOUND keeps the existing 'not found' failed status, any other non-success returns a new failed status carrying result.message, and the success path is unchanged; test_ops_group_assignment_handler.py gains the new non-NOT_FOUND-failure case
- [ ] #3 jobs/revoke_aws_sso_access.py uses build_identity_center_adapter().get_user_id(); a non-success result is logged with status and error_code, skips delete_account_assignment and expire_request for that request, and the loop continues to the next request; the pinned RuntimeError-side_effect test in test_revoke_aws_sso_access.py is replaced with a non-success OperationResult case
- [ ] #4 none of the three files import integrations.aws.identity_store
- [ ] #5 ruff, mypy (no new errors) and pytest pass with output recorded; a grep of these three files shows zero references to integrations.aws.identity_store
<!-- AC:END -->
