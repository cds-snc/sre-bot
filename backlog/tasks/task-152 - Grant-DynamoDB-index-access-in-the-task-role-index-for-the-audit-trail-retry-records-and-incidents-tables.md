---
id: TASK-152
title: >-
  Grant DynamoDB index access in the task role: /index/* for the audit trail,
  retry records and incidents tables
status: To Do
assignee: []
created_date: '2026-10-14 23:08'
updated_date: '2026-10-14 23:20'
labels:
  - terraform
  - infrastructure
  - iam
dependencies: []
references:
  - terraform/iam.tf
  - decisions/cloud-portability.md
priority: medium
type: task
ordinal: 386000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The task role's DynamoDB statement (terraform/iam.tf:38-60) lists table ARNs only. A Query on a global secondary index is authorized against the index ARN (<table arn>/index/<name>), so every GSI read is denied today.

Latent, not live (verified 2026-10-14):
- Audit trail reads query user_email-timestamp-index and correlation_id-index (app/infrastructure/audit/service.py:214,243). The read methods have no production caller.
- Retry records query status-next_retry_at-index (app/infrastructure/resilience/retry/dynamodb_store.py:153,430,475). The retry backend defaults to memory (app/infrastructure/configuration/infrastructure/retry.py:60-61).
- The incidents table gains the by_channel and open GSIs in TASK-145.5.1, and its first index read lands with TASK-145.5.5.

THIS TASK
- terraform/iam.tf: add "${arn}/index/*" for sre_bot_audit_trail, sre_bot_retry_records and incidents. Index access is granted per table that has or is about to get a GSI, never as a wildcard over all tables.
- Any later table that gains a GSI adds its own index ARN in the same change (TASK-140.11 for the status-updates table).
- No application change. Standalone merge; tf_apply before TASK-145.5.5 merges.

Bottom layer of Stack K (handoff doc-13).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 terraform/iam.tf has a separate statement allowing only dynamodb:Query on <table arn>/index/* for sre_bot_audit_trail, sre_bot_retry_records and incidents; the table statement and every other table's indexes are unchanged
- [ ] #2 After the apply, aws iam simulate-principal-policy for the sre-bot-ecs-role returns allowed for dynamodb:Query on an audit trail index ARN and implicitDeny for an index ARN of a table not in the list; the output is recorded in the notes
- [ ] #3 terraform fmt -check passes and tflint reports no finding in iam.tf (baseline on main 2026-10-14: 7 pre-existing warnings, none in iam.tf), and the tf_plan comment on the PR shows only the change to the sre-botSecretsManagerKeyRetrieval policy document
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Layer 1 of Stack K (handoff doc-13). One file, about 10 HCL lines; well under the size gate.

Context (verified 2026-10-14)
- The task role sre-bot-ecs-role (terraform/iam.tf:72-75, used as task_role_arn in terraform/ecs.tf:17) gets DynamoDB access from the third statement of data.aws_iam_policy_document.sre-bot_secrets_manager (terraform/iam.tf:38-60), which lists table ARNs only. DynamoDB authorizes a Query on a secondary index against <table arn>/index/<name>, so GSI reads are denied.
- Tables with GSIs: sre_bot_audit_trail (terraform/dynamodb.tf:125, two GSIs), sre_bot_retry_records (dynamodb.tf:181, one GSI); incidents (dynamodb.tf:91) gains two in TASK-145.5.1. A grant on an index pattern that matches nothing yet is valid.
- terraform/ applies only to production: tf_apply.yml runs terragrunt apply on every push to main touching terraform/**; tf_plan.yml comments the production plan on the PR. There is no non-production account, so the post-apply check is a policy simulation, not a live query.

Steps
1. terraform/iam.tf: add a fourth statement to data.aws_iam_policy_document.sre-bot_secrets_manager, after the table statement:
   effect Allow; actions [dynamodb:Query]; resources ["${aws_dynamodb_table.incidents_table.arn}/index/*", "${aws_dynamodb_table.sre_bot_audit_trail.arn}/index/*", "${aws_dynamodb_table.sre_bot_retry_records.arn}/index/*"].
   Query only: no code path scans an index, and the records contract has no scan. A separate statement keeps index access visibly narrower than table access.
2. Local checks from terraform/: terraform fmt -check; tflint reports no new finding (7 pre-existing warnings on main, none in iam.tf). (terraform validate needs terragrunt init against the production backend; tf_plan on the PR covers it.)
3. PR: the tf_plan comment must show only the policy document diff (the three index ARNs). Merging applies it.
4. After the apply (human, read-only): aws iam simulate-principal-policy --policy-source-arn <sre-bot-ecs-role ARN> --action-names dynamodb:Query --resource-arns <audit trail table ARN>/index/correlation_id-index <webhooks table ARN>/index/x. Expect allowed and implicitDeny. Record the output in the notes.

AC -> step: AC1 step 1; AC2 step 4; AC3 steps 2-3.
Tests: no application code changes, so no pytest change; the Python gates still run (ruff, mypy, pytest) to show the layer leaves main green.

Assumptions and doubts
- Index ARN format and authorization: AWS documents the index resource as table/<name>/index/<index>; confirmed again by the simulation in step 4.
- A wildcard per table (index/*) rather than per named index: indexes are declared in code next to each RecordTable, and naming each one here would make every index change a second IAM edit. Scoped to three tables, not to all.
- TASK-140.11 adds its own table's index ARN when it adds a GSI (note recorded on TASK-140.11).

Blast radius and rollback
- Only adds an Allow; no existing access can be lost. No application or deploy change.
- One git revert followed by the automatic apply removes it. The grant must exist before TASK-145.5.5 merges, which is the first production index read.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-14 23:20
---
2026-10-14 (human): plan approved.
---
<!-- COMMENTS:END -->
