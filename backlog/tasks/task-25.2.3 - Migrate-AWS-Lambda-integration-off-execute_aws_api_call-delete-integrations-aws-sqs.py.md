---
id: TASK-25.2.3
title: >-
  Build the Identity Center adapter and migrate its legacy callers; delete
  integrations/aws/identity_store.py
status: To Do
assignee: []
created_date: '2026-07-31 18:48'
updated_date: '2026-09-11 19:20'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.2
references:
  - app/integrations/aws/identity_store.py
  - app/integrations/aws/client.py
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - app/packages/incident/drive/adapters/google_drive.py
parent_task_id: TASK-25.2
priority: high
ordinal: 120000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-25.2, done first among the adapters because Identity Center has the most callers and the only non-trivial composition. Create packages/aws_platform/adapters/identity_center.py: holds the typed identitystore client from get_aws_client("identitystore", role_arn=...), resolves the identity store id from settings, exposes the operations legacy callers use (healthcheck, create_user, delete_user, get_user_id, describe_user, list_users, get_group_id, list_groups, create_group_membership, delete_group_membership, get_group_membership_id, list_group_memberships, list_groups_with_memberships), paginates through client.get_paginator, wraps each SDK call in try/except + classify_aws_error and returns OperationResult. The groups-with-memberships join and its utils.filters usage move into the adapter with the call; no other business logic is added. Non-idempotent writes (create_user, create_group_membership) are evaluated for the retries-disabled factory option.

Callers migrated (starting list, re-grep before planning): modules/aws/identity_center.py, modules/aws/aws.py, modules/aws/aws_access_requests.py (get_user_id only), modules/aws/ops_group_assignment.py (get_group_id only), modules/provisioning/users.py, modules/provisioning/groups.py, jobs/revoke_aws_sso_access.py (get_user_id only), jobs/scheduled_tasks.py (healthcheck). Each caller branches on OperationResult; the resulting behaviour where it previously received False is documented per call site in notes for human review.

Deleted with the last caller: integrations/aws/identity_store.py and tests/integrations/aws/test_identity_store.py; tests/integration/integrations/aws/test_identity_store_conformance.py is retargeted at the adapter (moto stays) or deleted if fully superseded by Stubber tests.

packages/access/sync/adapters/aws_identity_center.py is not reused: it exposes platform-sync operations (ensure_user, apply_entitlement, reconcile), not the raw Identity Store calls needed here. The access feature is not enabled yet; its own migration onto whatever shared Identity Center adapter emerges is later work, not a shim built here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/aws_platform/adapters/identity_center.py returns OperationResult from every operation, builds its client only through get_aws_client, and has botocore Stubber unit tests for each operation plus classification paths
- [ ] #2 The eight listed caller files no longer import integrations.aws.identity_store; each handles OperationResult explicitly, with per-call-site error-path behaviour recorded in notes and reviewed
- [ ] #3 integrations/aws/identity_store.py and its legacy tests are deleted; both guard baselines are pruned of identity_store entries
- [ ] #4 packages/access is not reworked; the access feature's own migration stays out of scope
- [ ] #5 Defect found by TASK-25.2.1's characterization pass is resolved deliberately, not carried across the seam: modules/aws/aws_access_requests.py's access_view_handler guards get_user_id with 'is None' although the integration only ever returns False, so its 'not registered with AWS SSO' reply is unreachable and a lookup failure flows into already_has_access and create_account_assignment with a False user id. With OperationResult, NOT_FOUND sends that reply and any other failure status stops before the assignment; the pinned characterization tests are updated to the new contract
- [ ] #6 jobs/revoke_aws_sso_access.py no longer passes a failed get_user_id result into delete_account_assignment: a non-success status ends the job step with an explicit log and result
- [ ] #7 modules/aws/aws.py's request_aws_account_access is unreferenced in production and calls create_aws_access_request with positionally shifted arguments (access_type receives a datetime, start_date_time receives the access type string); it is deleted, or fixed if the planner finds a live caller, with the pinned test removed or corrected accordingly
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-11 16:19
---
2026-09-11: three defects surfaced by the TASK-25.2.1 characterization pass were assigned here as explicit ACs (unreachable 'not registered' branch, revoke job forwarding False, dead request_aws_account_access with shifted positional args) so they are fixed or deleted deliberately when these call sites move to OperationResult, rather than pinned forever.
---

created: 2026-09-11 19:20
---
2026-09-11 planning: split under the single-PR size gate (estimate ~12 production files mixing new adapter code, a behaviour-changing caller migration and a 379-line deletion). 25.2.3 stays the coordinator with its ACs unchanged: AC#1 and AC#4 are delivered by TASK-25.2.3.1 (adapter + Stubber tests + ConflictException mapping, on branch feat/aws_identity_center_adapter); AC#2, #3, #5, #6, #7 by TASK-25.2.3.2 (caller migration, defect resolution, deletion, baseline pruning). Human decisions recorded on the subtasks: retries=False client for the two creates; ConflictException -> PERMANENT_ERROR; healthcheck = single-page ListUsers succeeds; provider build_identity_center_adapter() in the adapter module; failed bulk listings raise the module-local Directory*UnavailableError; access_view_handler reuses the existing 'Failed to provision' reply for non-NOT_FOUND failures; revoke job logs and skips on any non-success. Finding: tests/integration/integrations/aws/test_identity_store_conformance.py targets packages/access's adapter via moto and never imports the legacy module, so it is not orphaned and stays untouched.
---
<!-- COMMENTS:END -->
