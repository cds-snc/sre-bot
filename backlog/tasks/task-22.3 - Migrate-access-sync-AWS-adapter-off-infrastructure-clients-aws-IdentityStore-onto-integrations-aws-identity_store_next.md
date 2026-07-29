---
id: TASK-22.3
title: >-
  Migrate access-sync AWS adapter off infrastructure/clients/aws IdentityStore
  onto integrations/aws/identity_store_next
status: To Do
assignee: []
created_date: '2026-07-29 21:11'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.2
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - app/packages/access/sync/providers.py
  - app/packages/access/sync/adapters/aws_identity_center.py
  - app/integrations/aws/identity_store_next.py
parent_task_id: TASK-22
priority: high
ordinal: 106000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-22 (parent). Repoint the access-sync AWS consumers off the deprecated AWSClients facade onto integrations/aws/identity_store_next.

Call sites: packages/access/sync/providers.py:3 (get_aws_clients, injected into AwsIdentityCenterAdapter at line ~37) and packages/access/sync/adapters/aws_identity_center.py:21 (AWSClients type). The adapter calls self._aws.identitystore.<method> at ~9 sites: list_users, list_groups, describe_group, get_user_id_by_username, create_user, delete_user, get_group_membership_id, create_group_membership, delete_group_membership. identity_store_next.py exposes matching MODULE-LEVEL functions returning OperationResult (verify each method name maps: e.g. get_user_id_by_username -> get_user_by_username; describe_group -> get_group). Adjust the adapter constructor/DI so it no longer receives an AWSClients facade. Preserve every OperationResult outcome and error_code normalization (e.g. ResourceNotFoundException -> NOT_FOUND) exactly. Wire to identity_store_next as-is (no _next rename = TASK-23; no raise/classify = TASK-25).

Test migration: relocate app/tests/integrations/aws/test_identity_store_next.py to app/tests/unit/integrations/aws/; keep packages/access/sync adapter tests in tests/unit and tests/integration as already located, updating any mock target paths. Legacy tests/integrations/ count must drop.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/access/sync/providers.py and adapters/aws_identity_center.py no longer import infrastructure.clients.aws; the adapter uses integrations/aws/identity_store_next
- [ ] #2 All access-sync adapter unit + integration tests pass behavior-neutral (same OperationResult status/error_code per method, including NOT_FOUND normalization)
- [ ] #3 test_identity_store_next.py relocated to tests/unit/integrations/aws/; any touched adapter tests remain correctly under tests/unit or tests/integration (legacy tests/integrations/ file count reduced)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Behavior-neutral: identity-store sync outcomes identical; PR references decisions/layers.md and decisions/outbound-clients.md
<!-- DOD:END -->
