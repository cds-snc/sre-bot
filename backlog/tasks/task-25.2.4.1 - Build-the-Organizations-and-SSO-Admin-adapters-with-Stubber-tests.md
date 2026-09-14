---
id: TASK-25.2.4.1
title: Build the Organizations and SSO-Admin adapters with Stubber tests
status: To Do
assignee: []
created_date: '2026-09-14 17:38'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4
references:
  - app/integrations/aws/organizations.py
  - app/integrations/aws/sso_admin.py
  - app/packages/aws_platform/adapters/identity_center.py
parent_task_id: TASK-25.2.4
priority: high
ordinal: 200000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1a of TASK-25.2.4 (build phase, expand only, no caller changes). Create packages/aws_platform/adapters/organizations.py and packages/aws_platform/adapters/sso_admin.py following the shape proven by packages/aws_platform/adapters/identity_center.py (typed client from get_aws_client, OperationResult returns, try/except + classify_aws_error, botocore.stub.Stubber tests). Organizations carries list_organization_accounts, get_account_details, get_account_tags and healthcheck (integrations/aws/organizations.py:12,53,67,80); get_active_account_names (organizations.py:22) and get_account_id_by_name (organizations.py:34) have zero production callers (re-grepped 2026-09-14, get_account_id_by_name's only caller was deleted by TASK-25.2.3.2.4) and are dropped, not ported. SSO-Admin carries create_account_assignment, delete_account_assignment and list_account_assignments_for_principal (sso_admin.py:33,65,94), each built with role_arn=settings.SERVICE_ROLE_MAP['sso-admin']; list_accounts_for_provisioned_permission_set (sso_admin.py:122) and get_predefined_permission_sets travel only if re-grep still shows zero callers -> re-verify before dropping, current grep shows none. No adapter provider registry: reuse the established build_<adapter>() factory-function pattern (e.g. build_organizations_adapter(), build_sso_admin_adapter()), not app/infrastructure/services/providers.py -- packages/aws_platform is the documented provisional seam (TASK-25.2 description, TIER RULES).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/aws_platform/adapters/organizations.py returns OperationResult from every operation, builds its client only through get_aws_client, and has Stubber unit tests for each operation plus classification paths
- [ ] #2 packages/aws_platform/adapters/sso_admin.py returns OperationResult from every operation, builds its client only through get_aws_client, and has Stubber unit tests for each operation plus classification paths
- [ ] #3 get_active_account_names and get_account_id_by_name are re-grepped for callers and dropped (not ported) if still unused; list_accounts_for_provisioned_permission_set is re-grepped and dropped if still unused
<!-- AC:END -->
