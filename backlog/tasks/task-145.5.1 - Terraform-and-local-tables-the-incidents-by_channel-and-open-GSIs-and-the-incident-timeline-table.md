---
id: TASK-145.5.1
title: >-
  Terraform and local tables: the incidents by_channel and open GSIs and the
  incident timeline table
status: Done
assignee: []
created_date: '2026-10-14 23:08'
updated_date: '2026-10-15 13:25'
labels:
  - incident
  - terraform
dependencies:
  - TASK-152
references:
  - terraform/dynamodb.tf
  - .devcontainer/dynamodb-create.sh
  - decisions/cloud-portability.md
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 387000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 2 of Stack K (handoff doc-13). Provisions the incident record layout decided on 2026-10-14 (TASK-145.5 plan). No application change.

THIS SLICE
- terraform/dynamodb.tf, incidents table (partition key id, unchanged):
  - GSI by_channel: partition channel_id (S).
  - Sparse GSI open: partition open_bucket (S, constant OPEN while the incident is open), sort opened_at (S, fixed-width ISO-8601 UTC with microseconds and +00:00). Items without open_bucket are absent from it.
  - Projection ALL on both. A KEYS_ONLY index would return key-only rows in production while InMemoryRecordStore returns full items, which breaks contract 4 of decisions/cloud-portability.md. Every existing GSI in the repo uses ALL.
  - Each GSI has its own read and write capacity, write capacity at least the table's (legacy logs appends are written to the index until TASK-145.9 moves the timeline out).
- New table sre_bot_incident_timeline: partition incident_id (S), sort entry_key (S) formatted '<posted_at ISO>#<entry_id>'. Added to the AWS Backup selection and to the task role's table ARNs.
- DynamoDB creates one GSI per UpdateTable call. The AWS provider sends one call per new index and waits for each to become ACTIVE, so both GSIs go in one apply; if the second create fails, re-running the apply completes it.
- .devcontainer/dynamodb-create.sh: creates the incidents table with both GSIs and the timeline table; for an existing local incidents table it adds the missing GSIs (update-table), because codespaces are not rebuilt. The script is run locally as part of this slice.
- Backup gap fixed here: sre_bot_access_requests and sre_bot_incident_status_updates were left out of the AWS Backup selection when they were added (#1142, #1544). The selection and the task role's table statement read one shared list of table ARNs, so a new table cannot be missed in one of them again.
- Standalone merge. tf_apply has no dev stage: merging applies to production, and that apply must finish before TASK-145.5.5 merges.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 terraform/dynamodb.tf declares the by_channel and sparse open GSIs on incidents with projection ALL and their own capacity, and the sre_bot_incident_timeline table keyed (incident_id, entry_key)
- [x] #2 The timeline table is in the backup selection and in the task role's table ARNs
- [x] #3 tf_plan shows only these changes, and the apply sequence (one or two steps) is recorded in the notes
- [x] #4 .devcontainer/dynamodb-create.sh creates both GSIs and the timeline table on a fresh run and adds the GSIs to an existing local incidents table; it was run locally and describe-table shows both indexes ACTIVE
- [x] #5 Every DynamoDB table is in the backup selection and the task role's table statement through one shared list of table ARNs, which adds sre_bot_access_requests and sre_bot_incident_status_updates to the backups
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Layer 2 of Stack K (handoff doc-13). Infra only: terraform/dynamodb.tf, terraform/iam.tf, .devcontainer/dynamodb-create.sh. No application change, no pytest change.

Context (verified 2026-10-14)
- terraform/dynamodb.tf:85-94 incidents_table: hash_key id, provisioned 2/2, only attribute id, no GSI. Tables here are plain provisioned, no PITR/SSE/tag blocks (tags come from provider default_tags in terraform/main.tf:4-40). Existing GSIs all projection ALL with explicit read/write capacity: audit trail 1/1 (dynamodb.tf:157-171), retry records 2/2 (dynamodb.tf:204-211).
- Backup selection: terraform/dynamodb.tf:244-252 (aws_backup_selection.sre_bot_backup_selection, explicit ARN list). It does not list sre_bot_access_requests or sre_bot_incident_status_updates today (pre-existing gap, out of scope here).
- Task role table ARNs: terraform/iam.tf:49-59 (third statement of sre-bot_secrets_manager). TASK-152 added the fourth statement, Query on <arn>/index/* for incidents, audit trail and retry records (iam.tf:62-72). incidents already has its index grant; the timeline table gets NO GSI so it needs no index ARN.
- Provider: hashicorp/aws 6.56.0 locked (terraform/.terraform.lock.hcl:4-5). CI: terraform 1.5.3, terragrunt 0.48.0 (.github/workflows/tf_plan.yml:9-10). tf_plan.yml runs on PR touching terraform/**, plans production only (role sre-bot-plan, matrix module terraform); tf_apply.yml runs terragrunt apply -auto-approve on push to main touching terraform/**. There is no dev stage for terraform: merge applies to production.
- Local script: .devcontainer/dynamodb-create.sh, bash, no set -e, per-table 'if table_exists X; then echo already exists; else create-table' (incidents block at lines 100-113). Invoked by app/Makefile:9 (dev-setup) and app/bin/db.sh:225 (reset). rg for sre_bot_incidents, incident_timeline and dynamodb-create finds no app code or test that asserts on the table list or the script (app/modules/incident/incident_document.py:103-126 only uses 'incident_timeline_update_*' as log event names). The table name is sre_bot_incident_timeline (no code references it yet; TASK-145.5.4 introduces it).

Apply sequencing decision (approved by the human 2026-10-14): ONE apply, no targeting or second commit.
- Provider source v6.56.0 internal/service/dynamodb/table.go, resourceTableUpdate: GSI creates are 'Phase 3', one conn.UpdateTable call per index ('Only 1 online index can be created simultaneously per table'), each followed by waitGSIActive; AttributeDefinitions for the table are sent with each create call. So two new global_secondary_index blocks in one apply are created sequentially and the provider waits for each to be ACTIVE; the DynamoDB one-GSI-per-UpdateTable limit is handled by the provider. Source: https://github.com/hashicorp/terraform-provider-aws/blob/v6.56.0/internal/service/dynamodb/table.go
- Capacity does not interact: only new indexes are added, no billing-mode or table capacity change, so Phase 1 (deletes) and Phase 2 (updates) are empty. New attributes (channel_id, open_bucket, opened_at) are added as attribute blocks in the same resource and travel with the create calls.
- Not found: a provider issue reporting the limit for multi-GSI adds on provider v6. The CloudFormation 'cannot perform more than one GSI creation' thread (https://www.repost.aws/questions/QUVnJDNa8mSLiocehq8VWthQ/cloudformation-deployment-issue-error-with-dynamodb-gsi-updates) applies to CloudFormation, not this provider. Residual risk: if the second create fails mid-apply, the state holds the first GSI and a re-run (push of any terraform/** change, or re-run of the tf_apply workflow) completes it. Table is tiny, so backfill is seconds.

GSI capacity decision (researched 2026-10-14): both GSIs provisioned read 1, write 2; the repo stays on provisioned mode.
- Write: AWS requires each GSI's write capacity to be at least the base table's, because a GSI short on write capacity throttles writes to the base table (GSI back-pressure): https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/gsi-throttling.html and https://repost.aws/knowledge-center/dynamodb-gsi-throttling-table. The table is at 2, so 2. With projection ALL, an index write costs the full item size in 1 KB units, and legacy incident items grow with every logs list_append (app/modules/incident/db_operations.py:173), so by_channel's write cost per update equals the base table's; writing less than the table's capacity would throttle the table. open only receives writes while an incident is open.
- Read: by_channel is read once per Slack incident command (lookup by channel) and open by the list and reconcile paths, a handful of reads a minute; 1 RCU (two eventually consistent 4 KB reads a second, plus up to 300 s of unused capacity kept as burst) covers that, as it does for the audit trail GSIs.
- Hot partition: open has a constant partition key (OPEN), so all its items sit in one partition. Fine at this volume (a partition serves up to 1,000 WCU / 3,000 RCU); revisit only if open incidents ever number in the thousands.
- Not changed here: switching tables to on-demand (AWS's recommendation for low, unpredictable traffic: https://aws.amazon.com/blogs/database/choose-the-right-throughput-strategy-for-amazon-dynamodb-applications/). Every table in the repo is provisioned; a billing-mode change belongs to all tables, not this slice.

Backup gap (decided by the human 2026-10-14: fix in this slice, since this layer edits the same lists): sre_bot_access_requests (#1142) and sre_bot_incident_status_updates (#1544, TASK-140.4) are in the task role's table statement but missing from the backup selection, so they are not backed up today. The two lists differ only by those two tables. Fix: one shared list, so a new table cannot be added to one and missed in the other.
- aws_access_requests (legacy) is in both lists but has no app reference and no local table in the devcontainer script; it stays as is here (deleting a production table is not a fix for this slice), see open question in the session.

Steps
1. terraform/dynamodb.tf, incidents_table: add attribute blocks channel_id (S), open_bucket (S), opened_at (S); add global_secondary_index by_channel (hash_key channel_id, projection ALL, read 1, write 2) and open (hash_key open_bucket, range_key opened_at, projection ALL, read 1, write 2). Write capacity 2 equals the table's (legacy appends are written to the index until TASK-145.9); read 1 as for the audit trail GSIs. Comment above each GSI states its purpose and that open is sparse (open_bucket = OPEN only while the incident is open).
2. terraform/dynamodb.tf: new resource aws_dynamodb_table.sre_bot_incident_timeline (name sre_bot_incident_timeline, hash_key incident_id, range_key entry_key, both S, provisioned 2/2 like the status-updates table, comment: entry_key = '<posted_at ISO-8601>#<entry_id>'). Placed after incidents_table.
3. terraform/dynamodb.tf: add `locals { dynamodb_table_arns = [...] }` listing every table ARN (the current nine plus sre_bot_incident_timeline), with a comment that every table goes here so it is backed up and reachable by the task role. aws_backup_selection.sre_bot_backup_selection resources = local.dynamodb_table_arns, which adds sre_bot_access_requests, sre_bot_incident_status_updates and sre_bot_incident_timeline to the backups.
4. terraform/iam.tf: the table statement resources = local.dynamodb_table_arns (adds sre_bot_incident_timeline). No index ARN (no GSI); the by_channel and open indexes are already covered by TASK-152's incidents index/* grant.
5. .devcontainer/dynamodb-create.sh: (a) incidents fresh create gets the two attribute definitions and --global-secondary-indexes JSON (same capacities/projection ALL, JSON style as the audit trail block); (b) add helper gsi_exists <table> <index> (describe-table piped to jq on .Table.GlobalSecondaryIndexes[].IndexName; jq is already used in app/bin/db.sh) and helper wait_for_active <table> <index> (poll describe-table until TableStatus and the index IndexStatus are ACTIVE, bounded retries, non-zero exit with message on timeout); (c) in the 'incidents table already exists' branch, for each of by_channel and open that is missing, call aws dynamodb update-table once per index (--attribute-definitions for that index's attributes, --global-secondary-index-updates Create=...) and wait_for_active before the next, so the script is idempotent and one GSI per call; (d) new block for sre_bot_incident_timeline in the existing create-if-missing style (attribute definitions incident_id/entry_key, 2/2). Header comment unchanged (schemas must match dynamodb.tf).
6. Local run (agent, in the devcontainer): bash .devcontainer/dynamodb-create.sh against the existing local DB (exercises the update-table path), run it a second time (idempotent: no create/update calls), then aws dynamodb describe-table for incidents and sre_bot_incident_timeline with --endpoint-url http://dynamodb-local:8000; additionally exercise the fresh path with a throwaway delete-table incidents + rerun (via app/bin/db.sh reset incidents, which recreates all tables). Record outputs in the notes. If dynamodb-local is not reachable from the session, say so and hand the exact commands to the human; do not check AC 4.
7. Local gates from terraform/: terraform fmt -check, tflint (baseline on main: 7 warnings, none in dynamodb.tf/iam.tf per TASK-152 notes; confirm no new). Python gates from app/ (ruff, mypy scoped to touched files = none, pytest tests --ignore=tests/smoke) to show main stays green; note the known local idempotency __pycache__ failure if present.
8. PR: tf_plan comment must show only: incidents_table in-place update (+3 attributes, +2 GSIs), sre_bot_incident_timeline create, backup selection in-place update (+3 resources: access requests, status updates, timeline; list order may also change), aws_iam_policy.sre-bot_secrets_manager in-place update (+1 ARN; order may also change). Record the plan summary and the chosen apply sequence (one apply) in the notes. After merge (human) confirm tf_apply log shows the two GSI creations sequenced, and aws dynamodb describe-table incidents shows both IndexStatus ACTIVE.

AC -> step -> verification
- AC1 (GSIs with ALL + own capacity, timeline table keyed incident_id/entry_key): steps 1-2; verified by tf_plan output (step 8) and terraform fmt/tflint (step 7).
- AC2 (timeline in backup selection and task role ARNs): steps 3-4; verified by tf_plan diff of the backup selection and policy document.
- AC5 (all tables backed up from one shared list): step 3-4; verified by the tf_plan diff (backup selection gains exactly the three tables, IAM gains only the timeline) and after the first nightly run by the human listing recovery points for the three tables.
- AC3 (tf_plan shows only these changes; apply sequence recorded): step 8 and the sequencing decision above; verified by the PR tf_plan comment, recorded in notes.
- AC4 (script creates both on fresh run and adds to existing table; run locally; ACTIVE): steps 5-6; verified by local run output and describe-table on both tables, plus the idempotent second run.
Every step maps to an AC (step 7 is the gate, step 8 evidences AC3).

Test matrix (infra: no pytest). Local script cases: existing incidents table without GSIs (update path, two sequential updates), fresh start (create path), re-run with both GSIs present (no-op), table with only one GSI present (adds only the missing one; simulate by deleting nothing, covered by logic review since DynamoDB Local cannot drop a single GSI without another update-table Delete call, which can be used: aws dynamodb update-table --global-secondary-index-updates Delete=... then re-run), timeline table already present (no-op), wait timeout path (read-through only). Repo tests: none assert on the table list or the script (rg above); no new test file.

Assumptions and doubts
- Provider 6.56.0 sequences multi-GSI adds (source cited above). Verify: tf_plan cannot show it; tf_apply log after merge shows two UpdateTable creations. Fallback if the second create fails: re-run apply (idempotent).
- DynamoDB Local supports update-table GSI create and reports IndexStatus ACTIVE. Verify in step 6.
- Write capacity 2 on both GSIs matches the table and covers legacy appends until TASK-145.9; read 1 is enough for single-incident lookups. Verify nothing else queries them yet (rg shows no code uses the indexes until TASK-145.5.5).
- The records contract needs no table-level change for projection ALL (decisions/cloud-portability.md contract 4). Verify when TASK-145.5.4 tests the fake against DynamoDB Local.
- Legacy writers (app/modules/incident) put items with channel_id already present on incidents, so by_channel backfills existing rows automatically; items lacking channel_id are simply absent from it. open index stays empty until TASK-145.7/145.5.7.

Blast radius and rollback
- Merge runs tf_apply against production (no dev stage). Adding a GSI backfills from the live table (small table, minutes at most) and consumes write capacity on the base table for the backfill; reads/writes continue meanwhile. Each added index raises base-table write cost slightly (every incidents write is also written to indexes where the key attribute exists).
- IAM change only adds one resource ARN to an allow statement. Backup selection adds three tables: the next 06:00 UTC run backs them up (small tables, extra AWS Backup storage only). Changing the selection's resources may replace aws_backup_selection (the provider treats it as ForceNew); a replaced selection only re-associates the same plan, existing recovery points stay in the vault. Verify at tf_plan.
- Nothing in the app uses the new indexes or table until TASK-145.5.4/145.5.5, so a bad apply cannot break running behavior. TASK-145.5.5 must not merge until this apply and TASK-152's apply have completed (both checked by describe-table / simulate-principal-policy).
- Rollback: git revert plus the automatic apply deletes the two GSIs (one per call, provider-sequenced) and DELETES the timeline table with its data. Safe while the timeline is empty (nothing writes it before TASK-145.9); after TASK-145.9 ships, a revert would destroy captured timeline entries, so restore a backup first or revert the writers first. Never revert this layer while TASK-145.5.5 is deployed (its index reads would fail). Local: db.sh reset incidents restores a local table to the script's schema.
- Size gate: estimated production diff ~45 HCL lines + ~90 bash lines in 3 files (excluding task file); subsystems: terraform plus a local dev script (config only, no app, no CI). Under 400 LOC / 10 files, one concern, revertible. Gate passes, no decomposition.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implementation 2026-10-15 (branch stack-k/task-145.5.1-incidents-gsis).
- terraform/dynamodb.tf: incidents gets attributes channel_id, open_bucket, opened_at and GSIs by_channel (hash channel_id) and open (hash open_bucket, range opened_at), both projection ALL, read 1 / write 2. New aws_dynamodb_table.sre_bot_incident_timeline (incident_id HASH, entry_key RANGE, 2/2). New locals.dynamodb_table_arns (all ten tables); aws_backup_selection.sre_bot_backup_selection.resources = local.dynamodb_table_arns (adds sre_bot_access_requests, sre_bot_incident_status_updates, sre_bot_incident_timeline).
- terraform/iam.tf: the table statement resources = local.dynamodb_table_arns (adds sre_bot_incident_timeline only). Index grant from TASK-152 unchanged.
- .devcontainer/dynamodb-create.sh: helpers gsi_exists, wait_for_active (30 x 1 s, error on timeout), add_gsi_if_missing (one update-table per index, waits ACTIVE); incidents fresh create includes both GSIs; existing incidents table gets missing GSIs; new sre_bot_incident_timeline block.
Local run (DynamoDB Local, -sharedDb, existing incidents table with 37 items, no GSIs):
- Run 1: 'Adding by_channel index ... added', 'Adding open index ... added', 'Creating sre_bot_incident_timeline table ... created'.
- Run 2: 'incidents index by_channel already exists', 'incidents index open already exists', 'sre_bot_incident_timeline table already exists' (no-op).
- One missing GSI: update-table Delete open, rerun: by_channel already exists, 'Adding open index ... added'.
- Fresh path: items exported by scan, delete-table incidents, rerun: 'Creating incidents table with GSIs... created'; 37 items written back (no UnprocessedItems).
- describe-table incidents: ACTIVE, by_channel ACTIVE (channel_id HASH, ALL, 1/2), open ACTIVE (open_bucket HASH, opened_at RANGE, ALL, 1/2), ItemCount 37; scan COUNT on by_channel = 37. describe-table sre_bot_incident_timeline: ACTIVE, incident_id HASH, entry_key RANGE.
Gates:
- terraform fmt -check: exit 0. tflint: exit 0, 7 warnings (baseline), none in dynamodb.tf or iam.tf.
- ruff check .: All checks passed. mypy: no Python file touched (0 in touched files).
- pytest tests --ignore=tests/smoke: 1 failed, 4884 passed. The failure is test_old_idempotency_package_is_not_discoverable, caused by the ignored local app/infrastructure/idempotency/__pycache__ directory (pre-existing, local only).
AC 3 pending: PR tf_plan comment and the apply sequence (one apply).

tf_plan on PR #1597 (commit 139b53c, 2026-10-15 12:51 UTC): Plan: 2 to add, 2 to change, 1 to destroy. add sre_bot_incident_timeline (incident_id HASH, entry_key RANGE, 2/2); update incidents_table (+3 attributes channel_id/open_bucket/opened_at, +2 GSIs by_channel and open, ALL, 1/2); update aws_iam_policy.sre-bot_secrets_manager (table statement gains the timeline ARN; whole document shows as known after apply because the new ARN is unknown until create); recreate aws_backup_selection.sre_bot_backup_selection (resources forces replacement; same plan and role, existing recovery points stay in the vault). Matches the expected change set.
The plan warned 'hash_key is deprecated. Use key_schema instead' (19 occurrences): provider 6.56.0 deprecates global_secondary_index.hash_key/range_key (table-level hash_key/range_key are not deprecated, per terraform providers schema). Fixed here per the deprecation rule: all five GSIs (by_channel, open, user_email-timestamp-index, correlation_id-index, status-next_retry_at-index) use key_schema blocks.
Plan-neutrality checked against DynamoDB Local with provider 6.56.0 (scratch config, deleted after): a table with a hash-only and a hash+range GSI created with hash_key/range_key, then the config switched to key_schema: terraform plan 'No changes'; switched back: 'No changes'. So existing audit trail and retry records indexes are not recreated. terraform validate: Success, no warnings. tflint: 7 warnings (baseline), none in dynamodb.tf or iam.tf. terraform fmt -check: exit 0.
AC 3 re-check pending on the new tf_plan: expected identical to the above, with no change on sre_bot_audit_trail or sre_bot_retry_records and no deprecation warning.
Apply sequence: one apply (provider creates the two GSIs one UpdateTable call at a time and waits for each ACTIVE; re-run tf_apply if the second create fails).

tf_plan re-check on PR #1597 (commit 6e67e67 after the stack sync, run 38740903494, comment 2026-10-15 13:14 UTC): Plan: 2 to add, 2 to change, 1 to destroy; same change set as the first plan: add sre_bot_incident_timeline; update incidents_table (+3 attributes, +2 GSIs by_channel and open, ALL, 1/2, now as key_schema blocks with hash_key shown as known after apply); update aws_iam_policy.sre-bot_secrets_manager (+1 table ARN); recreate aws_backup_selection.sre_bot_backup_selection. sre_bot_audit_trail and sre_bot_retry_records appear only as ARNs in the policy and backup lists; neither table resource changes, so the key_schema move is plan-neutral in production.
No hash_key deprecation warning. The only warning is 'Argument is deprecated' in module sre_bot_bucket (server_side_encryption_configuration) 'and 2 more similar warnings'. Terraform groups warnings by summary, so the module's other two deprecated arguments were checked against the provider 6.56.0 schema: the module sets exactly three deprecated aws_s3_bucket arguments (acl default 'private', versioning, server_side_encryption_configuration), which accounts for all three. Pre-existing upstream module (cds-snc/terraform-modules S3 v11.3.3), out of scope.
The stack sync pushed #1595 and #1597 at the same time; #1595's tf_plan (run 38740902073, attempt 1) lost the shared production state lock to the run above and failed, and its re-run passed. Not a config failure.
AC 3 met: plan shows only this layer's changes; apply sequence is one apply (recorded above).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-14 23:58
---
Plan approved by the human 2026-10-14 (decisions: one apply; GSIs read 1 / write 2; backup gap fixed through one shared table ARN list, AC 5). aws_access_requests stays as is: unused today, may serve the access feature enhancements; revisit when that work starts.
---
<!-- COMMENTS:END -->
