---
id: TASK-25.2.4
title: >-
  Migrate Organizations/SSO-Admin + legacy (non-_next) Identity Store consumers
  off execute_aws_api_call
status: To Do
assignee: []
created_date: '2026-07-31 18:49'
updated_date: '2026-08-04 19:39'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.3
  - TASK-22.3
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/aws/organizations.py
  - app/integrations/aws/sso_admin.py
  - app/integrations/aws/identity_store.py
  - app/integrations/aws/client.py
parent_task_id: TASK-25.2
priority: high
ordinal: 121000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 (largest, done last) of TASK-25.2. Migrate integrations/aws/{organizations,sso_admin}.py off execute_aws_api_call/handle_aws_api_errors onto get_aws_client + classify_aws_error (new instances for organizations/sso-admin); migrate integrations/aws/identity_store.py (a SEPARATE consumer set from TASK-22.3's packages/access/sync scope) reusing the SAME get_aws_client("identitystore")/classify_aws_error instance TASK-22.3 built (not a new one). These 3 services share a tightly-coupled consumer set (grep-confirmed 2026-07-31, done together deliberately rather than as 3 separate PRs to avoid repeatedly touching the same ~8 files): modules/aws/aws_access_requests.py, modules/aws/ops_group_assignment.py, modules/aws/aws.py, modules/aws/aws_account_health.py (organizations only), modules/aws/spending.py (organizations only), jobs/revoke_aws_sso_access.py, modules/aws/identity_center.py, modules/provisioning/users.py, modules/provisioning/groups.py, jobs/scheduled_tasks.py. Done last so the get_aws_client/classify_aws_error extraction pattern is proven on 3 smaller/isolated slices first. Once this slice lands, integrations/aws/client.py's execute_aws_api_call/handle_aws_api_errors should have zero remaining callers repo-wide - delete integrations/aws/client.py itself as the final step (feeds TASK-25.2's own coordinator AC#1).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/aws/organizations.py and sso_admin.py no longer call execute_aws_api_call/handle_aws_api_errors; identity_store.py is repointed onto TASK-22.3's existing get_aws_client("identitystore")/classify_aws_error instance (not a new one)
- [ ] #2 All identified consumer files behave per the raise+classify contract explicitly (no silent False-swallowing); resulting error-path behavior documented and human-reviewed per file, not assumed zero-diff
- [ ] #3 integrations/aws/client.py is deleted (zero remaining execute_aws_api_call/handle_aws_api_errors callers repo-wide, verified via grep)
- [ ] #4 moto-backed integration conformance test(s) under app/tests/integration/ exercise organizations.py's list_accounts/describe_account/list_tags_for_resource, sso_admin.py's create_account_assignment/delete_account_assignment/list_account_assignments_for_principal/list_accounts_for_provisioned_permission_set, and identity_store.py's ops already covered by TASK-22.3's suite (excluding get_group_membership_id, which moto does not implement) against real semantics via moto.mock_aws(), additive alongside existing MagicMock-based unit tests
<!-- AC:END -->
