---
id: TASK-25.2.3.2.2
title: Migrate modules/aws/identity_center.py onto the Identity Center adapter
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
  - app/modules/aws/identity_center.py
  - app/modules/provisioning/entities.py
  - app/modules/provisioning/users.py
  - app/packages/aws_platform/adapters/identity_center.py
  - decisions/outbound-clients.md
parent_task_id: TASK-25.2.3.2
priority: high
ordinal: 195000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-25.2.3.2 (split 2026-09-11 under the single-PR size gate). Migrates modules/aws/identity_center.py off integrations.aws.identity_store onto build_identity_center_adapter(): the two direct list_users() calls in synchronize() (:70, :79), raising DirectoryUsersUnavailableError (imported from modules.provisioning.users) on a non-success result; and the four create_user/delete_user/create_group_membership/delete_group_membership callables passed to entities.provision_entities at :155/:171/:261/:282/:329/:348. entities.provision_entities itself is unchanged (it tests 'if response:' and an OperationResult is always truthy), so this slice adds small local bridge functions that map the provision_entities entity-dict kwargs to adapter arguments and return result.data on success or False (logged with status and error_code) on any non-success -- preserving the legacy False-swallow contract so failed entities are still recorded as failed and the loop continues. Per the ConflictException human decision on TASK-25.2.3.1: create_user/create_group_membership conflicts now arrive as OperationResult(status=PERMANENT_ERROR) instead of a raised ClientError; the bridges' generic non-success handling already treats this as a failed (not crashing) entity -- document this explicitly at these two call sites.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 synchronize()'s two list_users() call sites use build_identity_center_adapter().list_users() and raise DirectoryUsersUnavailableError on a non-success result
- [ ] #2 four local bridge functions (create_user, delete_user, create_group_membership, delete_group_membership) wrap the adapter, map entity-dict kwargs to adapter arguments, and return result.data on success or False (logged with status and error_code) on non-success, including the PERMANENT_ERROR conflict case for create_user and create_group_membership
- [ ] #3 the four entities.provision_entities call sites (create/delete users and group memberships) pass the new local bridges instead of identity_store.*; entities.py itself is unchanged
- [ ] #4 modules/aws/identity_center.py no longer imports integrations.aws.identity_store
- [ ] #5 tests/unit/modules/aws/test_identity_center_handler.py is retargeted to patch build_identity_center_adapter, with new cases covering each bridge's success, non-success, and PERMANENT_ERROR-conflict paths, plus synchronize()'s DirectoryUsersUnavailableError path
- [ ] #6 ruff, mypy (no new errors) and pytest pass with output recorded; a grep of this file shows zero references to integrations.aws.identity_store
<!-- AC:END -->
