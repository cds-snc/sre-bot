---
id: TASK-145.7.1
title: >-
  Incident bindings table, its by_conversation index and IAM grant;
  incident-management.md A1
status: Done
assignee: []
created_date: '2026-11-09T19:05:00Z'
updated_date: '2026-11-10T15:11:00Z'
labels:
  - incident
  - terraform
dependencies: []
references:
  - decisions/incident-management.md
  - terraform/dynamodb.tf
parent_task_id: TASK-145.7
priority: high
type: task
ordinal: 498000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L0 (storage expand; the only new table in TASK-145). Terraform adds sre_bot_incident_bindings (hash incident_id, range binding_key '<kind>#<system>#<tenant>#<vendor_id>', sparse GSI by_conversation on conversation_id, projection ALL), adds it to local.dynamodb_table_arns and grants Query on its index. decisions/incident-management.md gets the A1 amendment listed in TASK-145.7's plan section 4 (Revisions 1-2, IncidentBinding, lookup order, marker rules 3-4 and 6, readers-before-writers ordering, revert window, severity-change and declare commit order). No app code reads the table yet. Merging applies terraform: the human runs bin/deploy-checks.zsh pre before merge and post after the deploy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 terraform/dynamodb.tf declares sre_bot_incident_bindings with hash incident_id, range binding_key and GSI by_conversation (hash conversation_id, projection ALL), point-in-time recovery and encryption as the timeline table; its arn is in local.dynamodb_table_arns
- [x] #2 terraform/iam.tf grants Query on the table's index/*; terraform fmt -check and validate pass
- [x] #3 decisions/incident-management.md carries the A1 clauses a-n of TASK-145.7's plan section 4 with one dated Changes line, and the 2026-11-06 line's waits for TASK-145.13 are revised (no wait on TASK-165.1 or TASK-146.3)
- [x] #4 deploy-checks pre and post outputs are recorded in the notes; no app code names the table
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-09 (human) with the Stack L program (TASK-145.7 plan). L0 in full: storage expand + A1
Branch stack-l/l0-incident-bindings-table from main. Files: terraform/dynamodb.tf, terraform/iam.tf, decisions/incident-management.md.
1. dynamodb.tf, after sre_bot_incident_status_updates (:73): resource aws_dynamodb_table sre_bot_incident_bindings, hash incident_id (S), range binding_key (S), attribute conversation_id (S), read/write capacity 2, GSI by_conversation hash conversation_id, projection ALL, read 1 / write 2; point_in_time_recovery and server-side encryption exactly as the timeline table; header comment: one item per working surface, sort key "<kind>#<system>#<tenant>#<vendor_id>", conversation_id only on chat bindings (sparse index).
2. dynamodb.tf local.dynamodb_table_arns (:262-272): add the arn (backup selection and the task role's table statement, iam.tf:36-46).
3. iam.tf:53-59: add "${aws_dynamodb_table.sre_bot_incident_bindings.arn}/index/*" to the Query-on-index resources.
4. decisions/incident-management.md, docs only (A1):
 a. Vocabulary (26): severity chosen by a person, may be unset at declare, changes as evidence arrives and each change is recorded, never computed from the number of products or teams; 0 per the handbook's criteria (Revision 1).
 b. The incident record (30): declaring binds at least one working surface (a chat conversation now, the Backstage page later); an active incident has one or more bindings, exactly one primary; commands find the incident through any bound conversation; IncidentBinding is a child record; "working surface" defined (where responders work the incident; unrelated to migration's rebuilt surfaces) (Revision 2).
 c. Stored form (38): lookup reads the bindings by_conversation index first, then channel_id/by_channel until TASK-145.13; source_alert is a message reference (conversation id, message id, url hint); record_version 1 = end-state shape, 2 = end-state shape with its binding; channel_id stays the lookup copy on new items.
 d. core/ owns (50): find_incident_for_conversation through any bound conversation; IncidentStore create (binding, then record) and updates; the binding store.
 e. System selection (77): resource failure at runtime leaves the reference empty and is reported; declare is unavailable only when no working surface can be bound (Revision 2's per-resource wording, runtime only: OQ9).
 f. Checks (103): declare writes the binding before the record; a binding without a record is not an incident; lookup prefers bindings, falls back to by_channel.
 g. Migration tolerated (121): channel_id and by_channel until the binding backfill is verified (TASK-145.13); the stale "served by a scan of the legacy table" fixed.
 h. Migration ordering (new rule): readers before writers. Every legacy reader of incident items is cut over before the rebuilt declare writes; writers write only the end-state shape; no dual-write; a write onto an item without the marker upgrades it first (upgrade-on-write, with its binding, marker 2) so no partial update stamps the marker (TASK-145.8 AC #7, if OQ approved).
 i. Rule 4 (136) amended: a later step may raise the marker on end-state items: guarded on the value read, side records first (idempotent conditional puts under deterministic keys), marker last, only items below its version. Rule 6 (138): legacy writers named (legacy declare until its cutover, recreate until its cutover, modules/dev/incident.py and the sheet import until TASK-145.12). "For incidents" (141): the binding step (one binding per item from its conversation map for the verified Slack tenant; open item without a conversation fails the run; Closed one only raised).
 k. Rules 3-4 amended (AC #7, OQ assessment): the job is the only batch runner; a writer may upgrade the single item it writes through the same function, under the same guard, in one update with its change (lazy upgrade plus backfill: MongoDB Schema Versioning pattern; version-conditioned writes).
 l. Revert window (OQ18): a data-shape cutover states whether its revert target reads the new shape; if not, the PR is forward-fix only after its first write (AWS Builders' Library, rollback safety: prepare readers, then activate writers).
 m. Severity changes (OQ13): the guarded field update, then a timeline entry with a deterministic id; a failed entry is logged and retried, never rolls the field back.
 n. Declare commit order (OQ6): conversation, binding, record (commit point); a failed conversation creates nothing to compensate; name_taken converges a retry (outbound-clients.md:26).
 j. Changes: one dated line (TASK-145.7 L0, A1).
Riding with later PRs: transport-slack.md alias mechanism (L1); System selection production sentence (L1); migration.md cutover bug-fix rule (L7a, OQ15); tolerated lines for the schedule-source adapter (owner 165.1) and the Notify trigger key (owner 165.1), and the 2026-11-06 Changes line on 145.13's waits revised (L9a); webhooks.md approximate acknowledged_count and the interim ack adapter (L9b).
5. Verification: terraform fmt -check and validate (cd terraform); rg proves no app code names the table. Human: zsh bin/deploy-checks.zsh pre before merge, post after the deploy (terraform and IAM change).
AC traceability: enabling work for AC #5 (re-worded) and for the A1 decisions; no AC is closed by L0. Tests: none (L2a adds the RecordTable-vs-terraform drift test). Rollback: one revert (terraform destroys the empty table, the grant goes). Ordering: deployed before L2a merges.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (L0 implemented, In Progress): terraform/dynamodb.tf adds sre_bot_incident_bindings (hash incident_id, range binding_key, attribute conversation_id, GSI by_conversation hash conversation_id projection ALL, read 1/write 2; blocks as the timeline table: no PITR or SSE block, backups through local.dynamodb_table_arns, where its arn is added); terraform/iam.tf grants Query on its index/*. terraform fmt -check and validate (init -backend=false) pass; rg finds no app code naming the table. decisions/incident-management.md A1: Vocabulary (Binding, severity Revision 1, system timeline entries), Bindings paragraph (cardinality, declare commit order, severity-change order), Stored form (record_version 1/2, bindings table and lookup order, source_alert message reference), core/ owns, System selection runtime clause, Checks test line, tolerated by_channel fallback (stale scan line replaced), rules 1 (readers before writers, revert window), 3 (upgrade on write), 4 (marker raise), 6 (legacy writers), the binding step, one Changes line withdrawing 145.13's waits on 165.1 and 146.3. Gates: ruff clean; contracts 13 kept; key ownership OK; package shape OK (3 baselined); test seams OK (47 + 12); mypy 41 errors, all pre-existing in legacy files; pytest 6666 passed. AC #4 waits on the human's deploy-checks pre and post outputs (gates AC #5 added for parity with the other Stack L subtasks).

2026-11-09: deploy-checks pre at 22:32:34Z (tmp/deploy-checks/pre-20261109T223234Z.txt), 30 s after #1841 merged (22:32:04Z, 95e47d46) and before its Terraform Apply finished, so it records the pre-change state: rollback target sre-bot-task:100, image 3075170b-2026-11-09, rollout COMPLETED 2/2; 24 h baseline 12 error lines (10 webhook_posting_error, 1 aws_identity_store_group_memberships_error, 1 payload_validation_error), none from this change. Terraform Apply (run 42712739853) success: 2 added, 1 changed, 1 destroyed = aws_dynamodb_table.sre_bot_incident_bindings created, aws_iam_policy.sre-bot_secrets_manager updated in place (the index Query grant), aws_backup_selection.sre_bot_backup_selection replaced (its resource list gains the table arn). No app deploy for this merge (terraform and docs only). AC #4 waits on deploy-checks post.

2026-11-10: deploy-checks post at 14:49:36Z (tmp/deploy-checks/post-20261110T144936Z.txt), checks=none: running sre-bot-task:100, image 3075170b-2026-11-09 unchanged (terraform-only merge, no app deploy), rollout PASS, boot_errors PASS, slack_up PASS, version PASS (head 3075170b), health 200; runtime_errors FAIL on one aws_identity_store_group_memberships_error (2026-11-09 23:59Z, access module, the same class as the 1 in the pre baseline; unrelated to this change, which no running code reads); non_json_lines WARN (4 known import-time lines). The bindings table and the index Query grant are live per Terraform Apply run 42712739853; git grep on origin/main (95e47d46) finds no app code naming incident_bindings. AC #4 checked; ready for the human to set Done.
<!-- SECTION:NOTES:END -->
