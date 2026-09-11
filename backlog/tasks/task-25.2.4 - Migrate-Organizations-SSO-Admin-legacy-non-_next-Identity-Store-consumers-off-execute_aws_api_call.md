---
id: TASK-25.2.4
title: >-
  Build the Organizations, SSO-Admin, Config, Cost Explorer, GuardDuty, Security
  Hub and Lambda adapters and migrate their callers; delete the seven mirrors
status: To Do
assignee: []
created_date: '2026-07-31 18:49'
updated_date: '2026-09-11 15:36'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.3
references:
  - app/integrations/aws/organizations.py
  - app/integrations/aws/sso_admin.py
  - app/integrations/aws/config.py
  - app/integrations/aws/cost_explorer.py
  - app/integrations/aws/guard_duty.py
  - app/integrations/aws/security_hub.py
  - app/integrations/aws/lambdas.py
  - app/integrations/aws/client.py
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
parent_task_id: TASK-25.2
priority: high
ordinal: 121000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-25.2. Create packages/aws_platform/adapters/{organizations,sso_admin,config,cost_explorer,guard_duty,security_hub,lambda}.py following the shape proven by TASK-25.2.3: typed client from get_aws_client (with the AUDIT/ORG/LOGGING/SSO role ARNs from settings where the mirror uses them today), SDK paginators, try/except + classify_aws_error, OperationResult returns, Stubber unit tests. Organizations' small helpers (active account names, account id by name) travel with the adapter. SSO-Admin's create/delete account-assignment status checks travel too; create_account_assignment is evaluated for the retries-disabled option.

Callers migrated (starting list, re-grep before planning): modules/aws/aws_access_requests.py, modules/aws/ops_group_assignment.py, modules/aws/aws.py, modules/aws/spending.py, modules/aws/aws_account_health.py, modules/aws/lambdas.py, jobs/revoke_aws_sso_access.py. Error-path behaviour is documented per call site.

Deleted with their last caller: integrations/aws/{organizations,sso_admin,config,cost_explorer,guard_duty,security_hub,lambdas}.py and tests/integrations/aws/test_{organizations,sso_admin,legacy_config,cost_explorer,guard_duty,security_hub,lambas}.py.

Size gate: seven small adapters (about 400 production LOC) plus seven caller files sit at the single-PR limit. The planner splits this into an Organizations + SSO-Admin subtask and an account-health + Lambda subtask if the plan exceeds it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The seven adapters exist under packages/aws_platform/adapters/, return OperationResult, build clients only through get_aws_client, and have Stubber unit tests
- [ ] #2 The seven listed caller files no longer import any of the seven mirrors and handle OperationResult explicitly, with error-path behaviour recorded in notes and reviewed
- [ ] #3 The seven mirror modules and their legacy tests are deleted and both guard baselines pruned accordingly
<!-- AC:END -->
