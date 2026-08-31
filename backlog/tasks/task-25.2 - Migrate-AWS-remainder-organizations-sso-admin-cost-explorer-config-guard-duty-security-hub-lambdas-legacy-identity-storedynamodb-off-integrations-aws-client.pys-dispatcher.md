---
id: TASK-25.2
title: >-
  Migrate AWS remainder
  (organizations/sso-admin/cost-explorer/config/guard-duty/security-hub/lambdas/legacy
  identity-store+dynamodb) off integrations/aws/client.py's dispatcher
status: To Do
assignee: []
created_date: '2026-07-31 18:48'
updated_date: '2026-08-31 18:52'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.2
  - TASK-22.3
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/aws/client.py
parent_task_id: TASK-25
priority: high
ordinal: 117000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Coordinator for the AWS-remainder slice of TASK-25. Confirmed via repo grep (2026-07-31): a THIRD, oldest AWS generation - integrations/aws/client.py's execute_aws_api_call/handle_aws_api_errors (distinct from both the deprecated infrastructure/clients/aws/ facade, already fully covered by TASK-22.1-22.5, and the _next generation tracked by TASK-23) - is still live and consumed by 9 services across 14 distinct production files, none in packages/: organizations (aws/aws_access_requests.py, aws/spending.py, aws/ops_group_assignment.py, aws/aws.py, aws/aws_account_health.py), sso_admin (aws/aws_access_requests.py, aws/ops_group_assignment.py, jobs/revoke_aws_sso_access.py), cost_explorer (aws/spending.py, aws/aws_account_health.py), config/guard_duty/security_hub (all only aws/aws_account_health.py), lambdas (aws/lambdas.py), identity_store - the NON-_next module, a separate consumer set from TASK-22.3's packages/access/sync scope (aws/aws_access_requests.py, aws/ops_group_assignment.py, aws/aws.py, aws/identity_center.py, provisioning/users.py, provisioning/groups.py, jobs/scheduled_tasks.py, jobs/revoke_aws_sso_access.py), dynamodb - the NON-_next module, a separate consumer set from TASK-22.2's infrastructure/storage scope (incident/incident_folder.py, incident/db_operations.py, slack/webhooks.py). integrations/aws/sqs.py has ZERO production consumers (confirmed) - delete outright. handle_aws_api_errors is worse than the Google equivalent: it SWALLOWS every exception and returns False, never re-raising - callers cannot distinguish a real error from a legitimate falsy/empty result today; migration must make this explicit (raise + classify) rather than preserve the silent-False behavior verbatim, flagged for human sign-off per subtask. This coordinator is Done only when all its per-cluster children are Done and integrations/aws/client.py itself is deleted (zero remaining callers).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 make client-usage-matrix / a repo-wide grep of execute_aws_api_call and handle_aws_api_errors sourced from integrations.aws.client shows zero call sites; integrations/aws/client.py is deleted
- [ ] #2 Every one of the 14 identified legacy consumer files is migrated onto get_aws_client + classify_aws_error (reusing the TASK-22.2/22.3 primitive and its DynamoDB/IdentityStore instances directly where the same service is involved, not reinventing), with each error path now raising/classifying instead of the current silent-False swallow - human-reviewed per subtask since this is a behavior change, not zero-diff
- [ ] #3 integrations/aws/sqs.py is deleted (zero production consumers, confirmed)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-08-31 18:52
---
Forward reference from TASK-23.2 planning (2026-08-31): the DynamoDB idempotency store keeps a conservative error-swallow on one path - a classified (mapped) SDK failure while re-reading a contended claim is downgraded to ClaimResult.IN_PROGRESS rather than raised. That was deliberately left as-is for TASK-23.2 and is flagged for reassessment during this AWS-remainder work, alongside the same question for other classify-and-continue call sites.
---
<!-- COMMENTS:END -->
