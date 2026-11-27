---
id: TASK-37.2.4
title: 'Webhooks slice 2.4: webhook inbox table (expand, empty)'
status: In Progress
assignee: []
created_date: '2026-11-27T16:46:00Z'
updated_date: '2026-11-27T18:19:00Z'
labels:
  - webhooks
  - terraform
  - migration
milestone: m-4
dependencies: []
references:
  - decisions/webhooks.md
  - decisions/reliability.md
  - decisions/deployment.md
parent_task_id: TASK-37.2
priority: high
ordinal: 555000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
doc-11 row 22.3a; a single PR from origin/main. Created at TASK-37.2.2 planning (2026-11-27, human-approved Q2). The inbox TASK-37.2.2 builds needs a table, and no task created one (webhooks.md Consequences names it as a cost).

Scope (terraform only, so tf_apply runs and no app image deploys, per deployment.md):
- aws_dynamodb_table sre_bot_webhook_inbox: partition item_key (S); TTL on expires_at; sparse GSI by_due (partition due S, sort due_at N) for the sweeper; sparse GSI by_instance (partition instance_ref S, sort received_at N, epoch milliseconds) for TASK-37.6.1's delivery list; projection ALL (the records contract returns full items from an index). Names match app/capabilities/webhooks/store.py.
- The existing webhooks table gains a sparse GSI by_instance_ref (partition instance_ref S, projection ALL), so the sweeper and the control plane find an instance by its internal reference, never by the URL token (added 2026-11-27 at TASK-37.2.2 implementation: the sweeper looks an item's instance up by instance_ref). Adding a GSI is an online operation; the table stays available while the index backfills, and only backfilled items enter it.
- The inbox table's ARN in local.dynamodb_table_arns (task-role IAM and backup selection); the task role's index permissions cover table/*/index/* for both tables.

Must merge before row 22.7 (TASK-37.4.2, which first mounts the route). The TASK-37.2.2 code reads the table name from [webhooks] inbox_table_name; this row adds no app code.
Blast radius: one empty table, one table ARN in the task role, and one index added online to the live webhooks table (legacy code ignores it). Rollback: a revert never destroys the table; removal is a removed block with lifecycle { destroy = false } (the SSM-name rule, TASK-145.7.13, applied to tables). bin/deploy-checks.zsh pre and post apply.
Change notice: none (nothing reads it).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 terraform/dynamodb.tf declares sre_bot_webhook_inbox with partition item_key, TTL on expires_at, and the sparse indexes by_due (due S, due_at N) and by_instance (instance_ref S, received_at N), each projecting every attribute; on-demand under the ceiling variables, point-in-time recovery for 7 days and deletion protection on (review + terraform plan)
- [x] #2 The webhooks table gains the sparse index by_instance_ref (instance_ref S, projection ALL) and moves to on-demand under the same ceiling, both in place with no table replacement (review + terraform plan)
- [x] #3 The inbox table's ARN is in local.dynamodb_table_arns, so the task role reaches it and its indexes, and the backup selection excludes it through not_resources with the reason in a comment (review + terraform plan)
- [ ] #4 The PR changes only terraform/, decisions/deployment.md, decisions/cloud-portability.md and its task file; terraform plan shows one table created, the webhooks table and the task-role policy updated in place, the backup selection replaced, and nothing else destroyed or replaced (check)
- [ ] #5 bin/deploy-checks.zsh pre runs before the merge and post after the apply, and the output is read (human run, agent reads)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Branch task-37.2.4-webhook-inbox-table from origin/main (3c196467). Doc-11 row 22.3a; waits on nothing; must merge before 22.7 (TASK-37.4.2). Terraform plus two ADR edits. tf_apply runs on the merge, and build_and_deploy ignores terraform/, decisions/ and backlog/, so no app image deploys. Re-planned 2026-11-27 after a program-scope assessment (R1-R10 below).

Names are fixed by app/capabilities/webhooks/store.py on stack-w/task-37.2.2-async-ingest (W3 #1898): table sre_bot_webhook_inbox ([webhooks] inbox_table_name), partition item_key; expires_at = epoch seconds (a valid TTL attribute); due = the constant "due" while the item is processing or retry, removed otherwise (RemoveAttribute, so the index stays sparse and no NULL key is written); due_at = epoch seconds; received_at = epoch milliseconds; instance_ref on both tables; indexes by_due, by_instance, by_instance_ref. The records store uses only PutItem, UpdateItem, GetItem, DeleteItem and Query, which the task role's table statement already grants. A throttled call is an [aws] transient code, so it answers 503, as webhooks.md Responses requires.

Steps
1. terraform/variables.tf: dynamodb_max_read_request_units and dynamodb_max_write_request_units (number, default 1000, validation > 0, described), the on-demand ceiling for every on-demand table (R2).
2. terraform/dynamodb.tf, new aws_dynamodb_table.sre_bot_webhook_inbox after webhooks_table, with a header comment naming store.py and webhooks.md section 3:
   - billing_mode PAY_PER_REQUEST with on_demand_throughput from the two variables (R1, R2)
   - hash_key item_key; attributes item_key S, due S, due_at N, instance_ref S, received_at N
   - ttl on expires_at
   - GSI by_due (hash due, range due_at, projection ALL); GSI by_instance (hash instance_ref, range received_at, projection ALL)
   - point_in_time_recovery { enabled = true, recovery_period_in_days = 7 } (equal to the [webhooks] inbox_ttl_seconds default) and deletion_protection_enabled = true (R3, R4)
   - default encryption at rest (R5)
3. terraform/dynamodb.tf, webhooks_table: billing_mode PAY_PER_REQUEST with the same ceiling (read_capacity and write_capacity removed); attribute instance_ref S; GSI by_instance_ref (hash instance_ref, projection ALL). No item has instance_ref until TASK-37.4.1 backfills it, so the index starts empty (R6).
4. terraform/dynamodb.tf: the inbox ARN in local.dynamodb_table_arns (task role and backup selection); aws_backup_selection gains not_resources = [inbox ARN], with a comment: the inbox is a 7-day delivery log, its retention is its TTL, and PITR covers recovery (R4).
5. terraform/iam.tf, the index statement: add "${aws_dynamodb_table.webhooks_table.arn}/index/*" and "${aws_dynamodb_table.sre_bot_webhook_inbox.arn}/index/*" (TASK-152 pattern).
6. decisions/deployment.md, a "Tables" paragraph with a Checks line and a Changes line (R7): tables are on-demand under the ceiling variables, and a table moves in the task that touches it; a new table sets deletion protection and PITR; every table is in the one ARN list, and a backup exclusion is explicit (not_resources) with its reason; a revert never destroys a table, and removal is a removed block (lifecycle { destroy = false }), then disabling deletion protection and a manual delete once nothing reads it. This supersedes "rollback: terraform destroys the empty table" (TASK-145.7.1).
7. decisions/cloud-portability.md (R8): Checks: each RecordTable has a drift test against terraform/dynamodb.tf (keys, indexes, expiry attribute), the TASK-145.7.3 practice made a rule. Consequences: expiry is a backend seam. The records contract has no expiry concept, DynamoDB TTL deletes typically within a few days, readers never rely on the deletion for correctness, and a backend without TTL needs a purge job. No contract field is added until a second backend exists (the anti-speculative rule). Changes line.
8. Local: terraform fmt -check -recursive terraform/; terraform -chdir=terraform init -backend=false; terraform validate. The PR's tf_plan job prints the plan AC #4 reads.
9. Task edits (CLI): AC #1 and #2 reworded (below); AC #4 reworded (R9); TASK-37.4.2 gains an AC: drift tests for instances_table and inbox_table (keys, indexes, ttl attribute, PITR period equal to the inbox_ttl_seconds default); TASK-37.3 gets a note (R5). doc-11 open decision for Lane A (R10).

ACs after approval
- #1 sre_bot_webhook_inbox: partition item_key, TTL on expires_at, sparse by_due (due S, due_at N) and by_instance (instance_ref S, received_at N), projection ALL; on-demand under the ceiling variables; PITR 7 days; deletion protection on
- #2 webhooks: sparse by_instance_ref (instance_ref S, projection ALL) and on-demand under the ceiling, both in place with no table replacement
- #3 the inbox ARN is in local.dynamodb_table_arns (the task role reaches the table and its indexes) and excluded from the backup selection with its reason
- #4 the PR changes only terraform/, decisions/deployment.md, decisions/cloud-portability.md and the task file; tf_plan shows 1 table created, webhooks and the task-role policy updated in place, the backup selection replaced (an association: recovery points stay in the vault, as on the TASK-145.7.1 apply), and nothing else destroyed or replaced
- #5 unchanged (deploy-checks pre and post; human runs, agent reads)

Decisions (R1-R10)
- R1 On-demand by default. ADR gap: no ADR sets a capacity mode, and every table is provisioned at 1-5 units. Prior: the 18.L8 apply throttled at 2 WCU on incidents and bindings (five runs, two of them with a console raise to 100 WCU), and Lane A has proposed an on-demand task, awaiting the human. Upcoming: the TASK-37.4.1 backfill writes every webhooks item, which would throttle the same way at 1 WCU. AWS calls on-demand "the default and recommended throughput option for most DynamoDB workloads". Cloud-portability holds: the contract is unchanged, and throttling maps to transient, then 503.
- R2 The ceiling is terraform variables with defaults, not a local, following configuration.md's intent (no plain constants; an organisation changes the value in configuration; TASK-170 moves deployment values to the organisation's repository) and the variables.tf precedent (landing_page_max_query_string_bytes). It defends against unrestricted resource consumption (OWASP API4:2023) until the TASK-49 rate limit lands.
- R3 Deletion protection and PITR on new tables (Security Hub FSBP DynamoDB.6 and DynamoDB.2). ADR gap. Prior conflict: TASK-145.7.1 planned PITR "as the timeline table", found none there and dropped it, and its rollback destroyed the table; this row's human-approved removal rule (TASK-37.2.2 Q2) reverses that, and R7 makes it an ADR rule.
- R4 The inbox's retention is its TTL. ADR gap: no data-retention rule exists. The 30-day AWS Backup plus PITR's 35-day default would keep envelopes about 5 times longer than webhooks.md's 7 days, and envelopes can hold personal data and, for the Notify leak kind, a leaked key. OWASP ASVS 4.0.3 8.3.8 asks for retention classification with automatic deletion. So: PITR 7 days (configurable 1-35; the price does not change with the period) and a not_resources exclusion from AWS Backup. A broader retention ADR is flagged, not written here.
- R5 Default encryption at rest. security.md covers it: storage encryption does not stop a reader of the table or a backup, so secrets get field encryption (TASK-197), and a table key would add KMS calls without closing that threat. Hand-off: TASK-37.3 planning decides whether the Notify revocation kind seals the leaked key in the stored envelope (TASK-197.2) or drops it once revoked.
- R6 The webhooks table moves to on-demand in this PR, because this PR touches it (R1's move-with-the-task rule, the configuration.md "migration rides with the work" pattern), and before TASK-37.4.1's backfill. The mode switch is online and can go back at any time.
- R7 deployment.md gains the Tables rule (step 6).
- R8 cloud-portability.md gains the drift-test check and the expiry seam (step 7). The drift tests themselves need app/tests, which would deploy the image, so they go to TASK-37.4.2 (22.7, the first row to mount the route, which waits on this row).
- R9 AC #4 was wrong: changing the ARN list replaces the backup selection (observed on the TASK-145.7.1 apply).
- R10 Lane A: proposal that its pending on-demand task cover every remaining table (on-demand under the ceiling, PITR, deletion protection, the backup rule), recorded in doc-11's open decisions. Lane B takes no task id for it.
- by_due's single "due" partition is a hot key only past about 1,000 writes/s, far above this workload.

Blast radius: one new table (empty until 22.7), the live webhooks table switched to on-demand with one empty index added online (legacy reads by id unchanged), the task-role policy updated in place, the backup selection replaced. No app deploy.
Rollback: a revert undoes the index, the mode and the IAM lines. It never destroys the table: deletion protection makes such an apply fail, so removal goes through a removed block PR (destroy = false). bin/deploy-checks.zsh pre before the merge, post after the apply.
Change notice: none (nothing reads the table or the index). Size: about 120 lines across 5 files plus the task file.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-27 (TASK-37.2.2 implementation): scope gains the sparse by_instance_ref index on the existing webhooks table. The sweeper reloads an item's instance by instance_ref, the only id an item may hold (the URL token is a credential and never stored), and TASK-37.6.1 addresses instances by instance_ref as well. Attribute names fixed to the code: item_key, expires_at, due, due_at, instance_ref, received_at (ms).

2026-11-27 (implementation): plan R1-R10 approved as recommended (human). terraform/variables.tf: the two on-demand ceiling variables (default 1000, validated > 0). terraform/dynamodb.tf: sre_bot_webhook_inbox (item_key; TTL expires_at; by_due due S/due_at N and by_instance instance_ref S/received_at N, projection ALL; PAY_PER_REQUEST with on_demand_throughput from the variables; PITR 7 days; deletion protection); webhooks moves to PAY_PER_REQUEST under the same ceiling and gains instance_ref S and by_instance_ref (projection ALL); the inbox ARN is in local.dynamodb_table_arns and excluded from the backup selection by not_resources, with the reason in a comment. terraform/iam.tf: index Query on webhooks/index/* and sre_bot_webhook_inbox/index/*. ADRs: deployment.md gains the Tables rule (capacity, protection, backups and retention, removal), a Checks line, two Consequences (the tolerated provisioned and unprotected tables; no general retention record) and a Changes line; cloud-portability.md gains the expiry seam and the table-declaration drift rule, a Checks line and a Changes line. Verified: terraform fmt -check -recursive passes; terraform init -backend=false and validate pass (Terraform 1.16.6, hashicorp/aws 6.74.0); the 182 app tests that read terraform/ pass. ACs #1-#3 checked on review and validate; the PR's tf_plan output confirms them under AC #4. No Python file changed, so the full mypy and pytest were not run. Hand-offs, kept in doc-11 rows 22.7 and 22.4 because W3 edits those task files: TASK-37.4.2 gains an AC for drift tests on instances_table and inbox_table (key, indexes, ttl attribute, PITR period equal to the inbox_ttl_seconds default); TASK-37.3 planning decides whether the Notify revocation kind seals the leaked key in the stored envelope (TASK-197.2) or drops it once revoked.
<!-- SECTION:NOTES:END -->
