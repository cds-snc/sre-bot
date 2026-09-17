---
id: TASK-25.2.5
title: >-
  Build the DynamoDB adapter for legacy callers and migrate webhooks and
  incident persistence; delete integrations/aws/dynamodb.py
status: To Do
assignee: []
created_date: '2026-09-11 15:36'
updated_date: '2026-09-17 20:41'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4
references:
  - app/integrations/aws/dynamodb.py
  - app/modules/slack/webhooks.py
  - app/modules/incident/db_operations.py
  - app/modules/incident/incident_folder.py
  - app/infrastructure/idempotency/dynamodb.py
  - decisions/outbound-clients.md
  - app/packages/aws_platform/adapters/aws_lambda.py
  - app/packages/aws_platform/adapters/identity_center.py
parent_task_id: TASK-25.2
priority: high
ordinal: 122000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-25.2. COORDINATOR: decomposed into five subtasks under the single-PR size gate (see the plan). This task's ACs are satisfied by its children.

Create packages/aws_platform/adapters/dynamodb.py, a thin adapter over the typed dynamodb client from get_aws_client("dynamodb"). It keeps the low-level AttributeValue request/response shapes legacy callers use, paginates through client.get_paginator and returns OperationResult. It holds a second client built with retries=False for writes that are not replay-safe (the identity_center.py precedent). It exposes only the operations the migrated callers use: scan, get_item, put_item and update_item. query, delete_item and list_tables have no caller once the dead helpers are dropped. DynamoDBStorageService is deliberately not adopted by these callers here (human decision 2026-09-11). TASK-37.1 (webhooks) and TASK-38 (incident) move them onto storage later, so the caller changes stay minimal.

Callers migrated (re-grepped 2026-09-15): modules/slack/webhooks.py, modules/incident/db_operations.py, modules/incident/incident_folder.py (store_update only). Their ~12 downstream callers (api/v1/routes/webhooks.py, modules/slack/webhooks_{create,list}.py, modules/sre/webhook_helper.py, modules/incident/{core,incident_alert,incident_helper,incident_status,information_display,information_update}.py, modules/dev/incident.py) are not changed.

Error policy (human decision 2026-09-15): the helper modules branch on OperationResult internally and keep their public return shapes.
- Non-success on a read raises after logging, so a failure is never mistaken for "not found": the /hook route stops answering 404 (SNS redelivers), and create_incident's duplicate check stops creating a second record.
- Not-found keeps returning None, and an empty scan keeps returning [].
- Helpers that already have a failure branch (create_webhook, create_incident, update_incident_field, store_update, log_activity) keep returning None/False with a log.
- Counter increments log and drop, so a counter never blocks webhook delivery.

Retry safety (decisions/outbound-clients.md item 25; human decision 2026-09-15): the two webhook counter increments (SET x = x + :inc) and log_activity's list_append are not replay-safe, so they go through update_item(retries=False). Every other legacy write replays safely. The full inventory is in the notes.

Idempotency store (from the TASK-25.2 comment #1; human decisions 2026-09-15): keep the fail-closed downgrade in infrastructure/idempotency/dynamodb.py, where a failed re-read of a contended claim returns ClaimResult.IN_PROGRESS. Its only production users are leases. Record the reason and add the missing test. Also fix the self-replay hazard in claim(): a lost success response plus an SDK retry makes our own claim look IN_PROGRESS. The classify-and-continue sites in infrastructure/resilience/retry/dynamodb_store.py are NOT in scope, because that store is not built in production (backend defaults to memory). They are recorded on TASK-59.

Local endpoint: the adapter relies on get_aws_client's AWS_ENDPOINT_URL_DYNAMODB gate (set in .devcontainer/docker-compose.yml) instead of the legacy ENVIRONMENT in (local, dev, ci) gate. That is the same behaviour infrastructure/storage and idempotency already have.

Deleted: integrations/aws/dynamodb.py and tests/unit/integrations/aws/test_dynamodb_local_endpoint.py. Endpoint-gate coverage already exists in tests/unit/integrations/aws/test_aws_client_factory_config.py:89-102. Both guard baselines are pruned.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 packages/aws_platform/adapters/dynamodb.py exposes scan, get_item, put_item and update_item returning OperationResult with AttributeValue shapes unchanged, builds its retrying and retries-disabled clients only through get_aws_client, and has Stubber unit tests (TASK-25.2.5.1)
- [x] #2 modules/slack/webhooks.py, modules/incident/db_operations.py and modules/incident/incident_folder.py reach DynamoDB only through the adapter. Non-success on a read raises after logging, while not-found keeps None/[]. Existing failure branches keep returning None/False with a log. The pinned False-return characterization tests are replaced, and per-call-site before/after behaviour is recorded in notes (TASK-25.2.5.2, TASK-25.2.5.3)
- [x] #3 The non-idempotent write inventory is recorded in notes; the two webhook counter increments and log_activity's list_append are sent with update_item(retries=False) (TASK-25.2.5.1-.3)
- [ ] #4 The idempotency store's fail-closed IN_PROGRESS on a failed claim re-read is kept, with the decision recorded and a unit test; claim() returns NEW when an SDK replay of its own conditional put fails the condition, via a per-call claim token (TASK-25.2.5.4)
- [x] #5 integrations/aws/dynamodb.py and tests/unit/integrations/aws/test_dynamodb_local_endpoint.py are deleted, both guard baselines are pruned, and no boto3.client or boto3.Session construction remains in production code outside integrations/aws/client.py (TASK-25.2.5.5)
- [x] #6 The packages/aws_platform transition seam is bounded by a freeze-baseline guard and its baseline, seeded with the production consumers that exist once the migrations have landed and wired as a make target, with TASK-88 named as its retirement owner (TASK-25.2.5.5)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
COORDINATOR PLAN. TASK-25.2.5 is split into 5 subtasks under the single-PR size gate, and its ACs are satisfied by their union. Ground truth was read on 2026-09-15 from integrations/aws/dynamodb.py, modules/slack/webhooks.py, modules/incident/db_operations.py, incident_folder.py:489-567, infrastructure/idempotency/{dynamodb,lease,factory}.py, integrations/aws/client.py, packages/aws_platform/adapters/{aws_lambda,identity_center}.py, the TASK-25.2.1 call-site inventory (items 24-39) and every downstream caller of the two helper modules.

WHY DECOMPOSED (size-gate evidence)
- As one PR the task would span three subsystems (Slack webhooks, incident, infrastructure/idempotency) plus an additive adapter plus a mechanical deletion. The gate says two subsystems, and it forbids mixing additive, behaviour-change and deletion work.
- LOC: adapter ~110; webhooks.py ~60 changed; db_operations.py plus store_update ~70 changed; idempotency ~20; deletion -164. Tests: 3 legacy suites (27 + 21 + 37 tests) plus 2 new adapter test files.
- The split follows the TASK-25.2.4 expand/migrate/contract precedent. Callers group by subsystem: webhooks alone, and the incident table's two files together.

SUBTASKS AND ORDER
1. TASK-25.2.5.1 (expand): build the adapter (scan/get_item/put_item/update_item, retrying + retries-disabled clients) with Stubber tests, and rename the .env.example endpoint variable. No caller changes.
2. TASK-25.2.5.2 (migrate, after .1): modules/slack/webhooks.py.
3. TASK-25.2.5.3 (migrate, after .1): modules/incident/db_operations.py and incident_folder.store_update.
4. TASK-25.2.5.4 (independent, can land any time): idempotency claim re-read decision and claim-token replay fix.
5. TASK-25.2.5.5 (contract, after .2 and .3): delete integrations/aws/dynamodb.py and its endpoint test, and prune both baselines.
Every slice keeps main green. .1 is unused code. .2 and .3 each revert alone, because the legacy module stays until .5. .4 touches one file. .5 runs only after the re-grep.

PATTERN REUSED (not reinvented)
- Adapter: aws_lambda.py structure (_map_sdk_exception, _call, get_paginator flattening, build_* factory at function entry, in-account). identity_center.py:296-306 precedent for a second retries=False client.
- Callers: branch on OperationResult inside the helper module and log status/error_code/error (the TASK-25.2.4.x _failure_fields idiom). Raised unclassified errors propagate.
- Tests: Stubber for the adapter only. Caller tests mock MagicMock(spec=DynamoDBAdapter) and keep their legacy file names.

HUMAN DECISIONS 2026-09-15 THAT SHAPE THE CHILDREN
- Error policy: reads raise on non-success; not-found keeps None/[]; existing failure branches keep None/False; counters log and drop.
- The 3 replay-unsafe writes go through retries=False.
- Idempotency re-read downgrade kept (fail-closed) with a test; claim self-replay fixed in this task.
- Retry-store swallow sites not in scope, since that store is unused in production. Recorded on TASK-59.

DEAD CODE DROPPED, NOT PORTED (re-grep at implementation)
- webhooks.delete_webhook, revoke_webhook, is_active; db_operations.get_incident: zero production callers.
- integrations.aws.dynamodb.query, delete_item, list_tables: no caller once the helpers above are gone.

AC TRACEABILITY
- AC#1 <- .1
- AC#2 <- .2, .3
- AC#3 <- .1 (retries routing), .2 (counters), .3 (log_activity); inventory in notes
- AC#4 <- .4
- AC#5 <- .5

VERIFICATION (every child PR, from app/)
uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' ; uv run pytest tests --ignore=tests/smoke (only the known order-dependent SNS/google-directory failures allowed). .5 also runs make check-sdk-typing and make check-vendor-package-contract.

BLAST RADIUS AND ROLLBACK
- .2: DynamoDB failures in /hook and the /sre webhooks admin surface now surface as a 5xx or a Bolt error instead of 404 or a silent empty list. The counters can drop one increment on throttling.
- .3: a failed incidents scan raises instead of crashing on len(False) or passing as "no incident". A throttled log_activity line is dropped and logged.
- .4: the claim item gains one attribute; the table schema is unchanged (attributes are schemaless, key unchanged). A lease replay is no longer stuck until TTL.
- Local development: callers reach dynamodb-local only through AWS_ENDPOINT_URL_DYNAMODB. The devcontainer already sets it; .1 renames the variable in .env.example. Production (ENVIRONMENT=production, unset variable) is unaffected.
- Each slice reverts with a single git revert.

OPEN QUESTIONS FOR HUMAN REVIEW
- None blocking. The implementation of .2 verifies that the /hook route's 5xx body stays generic (TASK-7).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Planning 2026-09-15 (human decisions; they apply to every TASK-25.2.5.x subtask):
1. ERROR POLICY: webhooks.py and db_operations.py branch on OperationResult internally and keep their public return shapes.
   - Non-success on a read raises after logging.
   - Not-found stays None, and an empty scan stays [].
   - Helpers with an existing failure branch (create_webhook, create_incident, update_incident_field, store_update, log_activity) keep returning None/False with a log.
   - Counter increments log and drop.
   - Rejected: passing OperationResult up to the ~12 callers (over the gate; TASK-37/38 rewrite them) and log-and-return-old-sentinels (failure stays indistinguishable from not-found).
2. NON-IDEMPOTENT WRITES: sent with update_item(retries=False) on the adapter's retries-disabled client (identity_center.py precedent). Rejected: keeping retries and recording a tolerated divergence.
3. IDEMPOTENCY RE-READ DOWNGRADE: kept fail-closed, with the reason documented and a unit test added.
4. EXTRA SCOPE:
   - Claim self-replay fix: in scope (TASK-25.2.5.4).
   - Retry-store classify-and-continue sites: out of scope, because the DynamoDB retry store is not built in production (RetrySettings.backend defaults to memory; create_retry_store, get_resilience_service and RetryWorker are only constructed in tests). Recorded as a comment on TASK-59, which already owns that store.
5. Existing TASK-25.2.4 decisions carry over: Stubber for adapter tests, fix simple bugs in touched files, legacy test names kept.

NON-IDEMPOTENT WRITE INVENTORY (AC#3; every DynamoDB write in production code, read 2026-09-15)
Legacy callers (migrated here):
- modules/slack/webhooks.py:70 increment_acknowledged_count "SET acknowledged_count = acknowledged_count + :inc": NOT replay-safe, double count -> retries=False (.2)
- modules/slack/webhooks.py:80 increment_invocation_count, same expression: NOT replay-safe -> retries=False (.2)
- modules/incident/db_operations.py:108 log_activity "SET logs = list_append(if_not_exists(logs, :empty_list), :logs)": NOT replay-safe, duplicate log entry -> retries=False (.3)
- modules/slack/webhooks.py:26 create_webhook put_item: full item with a client-generated uuid, so a replay rewrites identical content. Safe.
- modules/incident/db_operations.py:40 create_incident put_item: full item with a model-generated id. Safe.
- modules/slack/webhooks.py:114 toggle_webhook "SET active = :active" (value precomputed before the call): safe under replay. The concurrent-toggle race is not a retry issue.
- modules/incident/db_operations.py:90 update_incident_field "SET #f = :f": safe.
- modules/incident/incident_folder.py:546 store_update "SET incident_updates = :updates" (precomputed): safe under replay. The read-modify-write race is left to TASK-38.
- delete_webhook delete_item: dead code, deleted (.2).
Infrastructure (already on get_aws_client, not migrated):
- infrastructure/idempotency/dynamodb.py:55 claim conditional put: a self-replay turns our own claim into IN_PROGRESS -> claim token (.4). :117 complete put (full item) and :134 release delete_item: safe.
- infrastructure/storage/service.py:99 put: safe. :138 put_if_not_exists has the same self-replay hazard, but it has no production caller today, so no action; it will be relevant to TASK-27.
- infrastructure/resilience/retry/dynamodb_store.py: not built in production; see TASK-59.

OTHER FINDINGS
- The legacy module picks the dynamodb-local endpoint from ENVIRONMENT in (local, dev, ci). get_aws_client uses AWS_ENDPOINT_URL_DYNAMODB instead, which .devcontainer/docker-compose.yml sets. CI sets ENVIRONMENT=ci, but its unit tests mock these callers. Production is unaffected. .1 renames the commented AWS_ENDPOINT_URL line in app/.env.example.
- No boto3.client/Session/resource construction remains in production code outside integrations/aws/client.py (rg 2026-09-15), so that part of the old AC#2 already holds and .5 re-verifies it.
- TASK-37.1 (webhooks StorageService store) and TASK-38 (incident package) rewrite these callers later, so the children keep their diffs minimal.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-14 14:05
---
2026-09-14 (human decision): modules/aws/aws_access_requests.py was removed from the caller list and from AC#2. It is dead in production and is deleted under TASK-25.2.3.2.4 with no code parity. The frontmatter reference to it is historical.
---

created: 2026-09-14 14:08
---
2026-09-14: title no longer mentions access-request persistence, and the aws_access_requests.py frontmatter reference was removed, following the re-scope above.
---

created: 2026-09-17 15:15
---
2026-09-17 (human decisions while planning TASK-25.2.5.5): two enabling subtasks added. TASK-25.2.5.7 retires the empty infrastructure.clients freeze guard. TASK-25.2.5.8 (after .7) extracts shared freeze-baseline plumbing and standardizes guard test names. TASK-25.2.5.5 now depends on .8 and builds the aws_platform seam guard on the shared module, wires it into CI, and generalizes decisions/migration.md rule 3. TASK-25.2.5.4 remains independent; parent AC#4 stays open until it lands.
---

created: 2026-09-17 19:36
---
CLOSE-OUT 2026-09-17 by TASK-25.2.5.5. ACs #1, #2, #3, #5 and #6 checked with traceability; #4 left unchecked and status left for a human (agents do not move a task to Done).

- #1 -> TASK-25.2.5.1 (DynamoDB adapter with Stubber tests).
- #2 -> TASK-25.2.5.2 (webhooks), TASK-25.2.5.3 (incident persistence) and TASK-25.2.5.6 (unclassified ClientError parity on the webhooks store).
- #3 -> TASK-25.2.5.1 through .3 (non-idempotent write inventory; retries=False on the two webhook counter increments and log_activity's list_append).
- #4 NOT CHECKED: owned by TASK-25.2.5.4 (idempotency store fail-closed claim re-read and claim token), still To Do, with no dependency in either direction on .5. It is the only parent AC outstanding.
- #5 -> TASK-25.2.5.5: integrations/aws/dynamodb.py (164 LOC) and tests/unit/integrations/aws/test_dynamodb_local_endpoint.py deleted; sdk_typing_antipatterns.txt 3 -> 2 entries and vendor_package_contract.txt 21 -> 20 entries, one line removed from each and every other entry byte-identical; boto3.client/Session/resource in production code now appears only in integrations/aws/client.py.
- #6 -> TASK-25.2.5.5: bin/check_aws_platform_seam.py built on bin/freeze_guard.py (TASK-25.2.5.8), baseline bin/baselines/aws_platform_seam_consumers.txt seeded with the 11 production consumers present after .2, .3 and .6, wired as make check-aws-platform-seam and as a CI step in ci_code.yml, with TASK-88 named as retirement owner in both the script docstring and the baseline header.

Two enabling subtasks were added under this parent while planning .5 and have since merged: TASK-25.2.5.7 (retire the empty infrastructure.clients freeze guard) and TASK-25.2.5.8 (extract the shared freeze-baseline plumbing, standardize guard test names). Neither maps to a parent AC; both exist so .5's guard work built on a single shared module instead of a fourth copy.
---

created: 2026-09-17 20:41
---
2026-09-17, from planning TASK-25.2.5.4.

REPOINTS A DANGLING POINTER IN THIS TASK'S NOTES. The non-idempotent write inventory says of infrastructure/storage/service.py:138 put_if_not_exists: "no production caller today, so no action; it will be relevant to TASK-27." Verified 2026-09-17 that neither TASK-27 nor TASK-27.1/27.2/27.3 records that hazard - TASK-27.2 names put_if_not_exists only as an existing Protocol operation. The finding had nowhere to land once this task closes. It now has its own task: TASK-103.

Three further tasks came out of planning .4, none of them in .4's scope:
- TASK-101: the orphan-lease window when the SDK exhausts its retries AFTER the conditional put landed. .4's claim token only rescues the replay that reaches ConditionalCheckFailedException; a run of transient failures exits through the RuntimeError at dynamodb.py:79 instead, with the lease held and no runner.
- TASK-102: release() and complete() write unconditionally, so a claimant whose TTL elapsed mid-run destroys the record of the holder that took over. Distinct from .4's hazard (mistaken identity, solved by an owner token) - this is staleness, and needs the token on the Protocol, which .4's AC#3 freezes.
- TASK-99 and TASK-100: decisions/reliability.md's rule that a Tier-2 lease is a duplication optimization and job bodies are idempotent regardless is a mandate the code does not meet - notify_stale_incident_channels double-posts an interactive nag into every stale incident channel. TASK-99 fixes the bodies; TASK-100 then flips the contended re-read to fail-open, which that doctrine actually implies. .4 keeps the fail-closed behaviour and records it in the docstring as provisional and lease-scoped.

Parent AC#4 is still owned by .4 and is still the only outstanding parent AC. None of the four new tasks blocks it.
---
<!-- COMMENTS:END -->
