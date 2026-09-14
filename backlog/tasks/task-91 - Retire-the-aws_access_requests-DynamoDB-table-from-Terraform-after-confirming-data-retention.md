---
id: TASK-91
title: >-
  Retire the aws_access_requests DynamoDB table from Terraform after confirming
  data retention
status: To Do
assignee: []
created_date: '2026-09-14 14:08'
labels:
  - infrastructure
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.2.3.2.4
references:
  - terraform/dynamodb.tf
  - terraform/iam.tf
priority: medium
ordinal: 198000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-25.2.3.2.4 (created 2026-09-14, human decision). TASK-25.2.3.2.4 deletes the dead AWS account access-request flow (modules/aws/aws_access_requests.py, the /aws access command, jobs/revoke_aws_sso_access.py) and its local-dev table setup. It deliberately leaves the production table in Terraform, because removing the resource destroys the table and any historical access-request records irreversibly. packages/access will re-provide the capability.

References left behind: terraform/dynamodb.tf aws_dynamodb_table.aws_access_requests_table (:13-29) and its entry in the aws_backup_selection resources list (:244); terraform/iam.tf:51 in the app role's DynamoDB statement. iam.tf also grants sre_bot_access_requests, which is not part of this cleanup.

Before removal, confirm with the owners (do not assume):
- whether the table's records (who requested access to which account, when, with what rationale) carry any audit-retention requirement;
- whether existing AWS Backup recovery points for the table must be retained or exported, and whether a final on-demand backup or export is taken first;
- whether any of the historical data should move into packages/access's storage (no migration is assumed).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The retention decision for the aws_access_requests records and their AWS Backup recovery points is recorded in notes, and any required export or final backup is taken before the resource is removed
- [ ] #2 terraform/dynamodb.tf no longer defines aws_access_requests_table or lists it in the backup selection, and terraform/iam.tf no longer grants the app role access to it; terraform plan output, recorded in notes, shows only the expected table destroy and the policy/backup-selection updates
- [ ] #3 A grep of terraform/ shows zero references to aws_access_requests
<!-- AC:END -->
