---
id: TASK-25.2.3.2
title: >-
  Migrate the eight Identity Center callers onto the adapter, resolve the three
  characterized defects, delete integrations/aws/identity_store.py
status: To Do
assignee: []
created_date: '2026-09-11 19:18'
updated_date: '2026-09-11 20:09'
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
- [ ] #1 The eight caller files no longer import integrations.aws.identity_store; each obtains the adapter through build_identity_center_adapter() at function entry and branches on OperationResult explicitly, with per-call-site error-path behaviour recorded in notes for review
- [ ] #2 modules/aws/identity_center.py bridges entities.provision_entities with a local unwrap: each create/delete callable maps the entity dict to adapter arguments and returns result.data on success or False on a non-success (logged with status and error_code), so failed entities are still recorded as failed; provision_entities itself is unchanged
- [ ] #3 synchronize and the AWS branches of provisioning/users.py and provisioning/groups.py raise DirectoryUsersUnavailableError / DirectoryGroupsUnavailableError carrying message and error_code when a listing fails; the pinned TypeError characterization tests are replaced by tests of the new contract
- [ ] #4 access_view_handler: a NOT_FOUND get_user_id sends the existing 'not registered with AWS SSO' reply; any other non-success falls to the existing 'Failed to provision' reply; already_has_access and create_account_assignment are not called on either failure; the two pinned tests are rewritten to the new contract
- [ ] #5 revoke_aws_sso_access: a non-success get_user_id logs status and error_code, skips delete_account_assignment and expire_request for that request and continues with the next; the pinned false-user-id test is replaced
- [ ] #6 request_aws_account_access and its three pinned tests are deleted (no production caller exists), and the now-unused get_account_id_by_name import is removed from modules/aws/aws.py
- [ ] #7 ops_group_assignment: NOT_FOUND keeps the existing 'not found' failed status; any other non-success returns a failed status carrying the result message; success path unchanged
- [ ] #8 jobs/scheduled_tasks.py registers lambda: build_identity_center_adapter().healthcheck().is_success under the 'aws' key, with the integration test retargeted
- [ ] #9 integrations/aws/identity_store.py and tests/integrations/aws/test_identity_store.py are deleted; the identity_store lines are removed from bin/baselines/sdk_typing_antipatterns.txt and bin/baselines/vendor_package_contract.txt; test_identity_store_conformance.py and packages/access are untouched
- [ ] #10 ruff, mypy (no new errors), pytest, make check-sdk-typing and make check-vendor-package-contract pass with output recorded; a repo-wide grep shows zero references to integrations.aws.identity_store
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-11 20:09
---
2026-09-11 carried over from TASK-25.2.3.1 for the caller migration: classify_aws_error now maps ConflictException to PERMANENT_ERROR (app/integrations/aws/client.py), where it previously propagated as a raised ClientError. When migrating each call site, account for that at every write that can conflict: create_user and create_group_membership in modules/aws/identity_center.py's provision_entities bridge (an 'already exists' conflict must be recorded as a failed entity and the sync must continue, matching the legacy False-swallow rather than aborting), and any other classify_aws_error consumer touched by the migration. Also verify packages/access's ensure_user path still behaves acceptably now that a conflict arrives as a result instead of an exception (the access feature is not enabled; document, do not rework). The per-call-site error-path notes required by AC#1 must state explicitly how a PERMANENT_ERROR conflict is handled at each site.
---
<!-- COMMENTS:END -->
