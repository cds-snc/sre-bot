---
id: TASK-23
title: 'Resolve every _next.py twin: one canonical client per vendor module'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-08-31 17:37'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.2
  - TASK-22.4
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - 'https://github.com/cds-snc/sre-bot/issues/1277'
priority: high
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/outbound-clients.md (Migration: "_next.py twins resolve into this shape"). Today app/integrations/ contains a fourth client generation: _next.py twins beside originals (aws/client_next.py, aws/dynamodb_next.py, aws/identity_store_next.py, google_workspace/google_directory_next.py, google_workspace/gmail_next.py, google_workspace/google_service_next.py).

Steps:
1. For each twin pair, diff the original vs _next and pick the survivor per the decided contract (clients raise typed SDK exceptions, SDK-native retry configured at construction, no hand-rolled retry, no OperationResult in clients).
2. Rename the survivor to the canonical name (no _next suffix), migrate its consumers, delete the loser. One vendor per PR.
3. Where neither twin matches the contract, converge on the closer one and fix it in the same PR (contract enforcement itself completes in task-25).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All three subtasks are Done: TASK-23.1 (Google _next deletion), TASK-23.2 (idempotency store convergence), TASK-23.3 (retry store convergence + AWS _next deletion)
- [ ] #2 find app/integrations -name '*_next.py' returns zero files
- [ ] #3 The _next-suffixed generation's string-dispatchers are gone: integrations/aws/client_next.py::execute_aws_api_call and integrations/google_workspace/google_service_next.py::execute_google_api_call no longer exist. Explicitly NOT in scope: the separate non-_next execute_aws_api_call (integrations/aws/client.py, TASK-25.2) and execute_google_api_call (integrations/google_workspace/google_service.py, TASK-25.1), each with many live consumers, and the get_google_api_command_parameters docstring scraper, which exists only in google_service.py (TASK-25.1). decisions/sdk-typing.md's repo-wide dispatcher and scraper checks pass only once TASK-25.1 and TASK-25.2 are also Done
- [ ] #4 The two remaining _next consumers (infrastructure/idempotency/dynamodb.py, infrastructure/resilience/retry/dynamodb_store.py) call a boto3 client from integrations.aws.client.get_aws_client inside try/except with classify_aws_error; claim/lease/dedup outcomes are unchanged and unmapped SDK exceptions propagate instead of being swallowed
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 No behavior change observable from feature code (existing tests green)
- [ ] #2 PR series references decisions/outbound-clients.md and decisions/sdk-typing.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
DECOMPOSED 2026-08-31 (task-planner). This task now COORDINATES three single-PR slices; it holds no code of its own. All TASK-22.x dependencies are Done, so the canonical primitives already exist and are proven in production code.

CANONICAL PRIMITIVES (verified in source, not assumed):
- AWS: integrations/aws/client.py::get_aws_client (boto3 Config(retries) + timeouts + dynamodb-local ENVIRONMENT gate + lazy AssumeRole) and classify_aws_error (returns (OperationStatus, error_code, retry_after); raises unmapped exceptions; maps ConditionalCheckFailedException -> PERMANENT_ERROR with the code preserved). Proven by infrastructure/storage/service.py (TASK-22.2) and packages/access/sync/adapters/aws_identity_center.py (TASK-22.3).
- Google: integrations/google_workspace/client.py::get_admin_directory_service + classify_google_error + execute_batch_request. Proven by infrastructure/directory/google.py (TASK-22.4).

CONSUMER INVENTORY (fresh repo-wide grep 2026-08-31, excluding backlog/, tmp/, caches):
- integrations/aws/dynamodb_next.py -> infrastructure/idempotency/dynamodb.py:15 (get_item/put_item/delete_item) and infrastructure/resilience/retry/dynamodb_store.py:16 (10 call sites at lines 124, 159, 219, 263, 309, 340, 386, 416, 429, 467).
- integrations/aws/client_next.py -> only dynamodb_next.py:27 and identity_store_next.py:26 (plus tests).
- integrations/aws/identity_store_next.py -> ZERO consumers.
- google_workspace/google_service_next.py, google_directory_next.py, gmail_next.py -> ZERO production consumers (only each other, their own tests, and tests/smoke/google_smoke_test.py:46).
Test-side references: tests/integrations/aws/{test_client_next.py, test_identity_store_next.py, fixtures_identity_store.py}, tests/unit/integrations/aws/{test_dynamodb_next.py, test_dynamodb_local_endpoint.py:57-87}, tests/unit/infrastructure/resilience/retry/{conftest.py:104, test_dynamodb_store.py, test_resilience_factory.py}, tests/integration/infrastructure/idempotency/conftest.py:12-13,33, tests/integrations/google_workspace/{test_google_service_next.py, test_google_directory_next.py}.

SIZE GATE: FAILED as a single PR. ~350 changed production LOC across two independent correctness-critical primitives (idempotency claim gate, retry-store claim/lease gate) plus ~1200 LOC of module deletions and ~2400 LOC of test deletions/rewrites; it also mixes a mechanical deletion with a real behavior change (gate rule 3). Decomposed with human approval into:

- TASK-23.1 (dep TASK-22.4) - delete the Google _next trio + their tests + the smoke-test import. Pure deletion, zero production consumers, independently shippable, no ordering constraint against the AWS slices. Ship first.
- TASK-23.2 (dep TASK-22.2) - converge infrastructure/idempotency/dynamodb.py onto get_aws_client + classify_aws_error, mirroring DynamoDBStorageService. dynamodb_next survives this slice.
- TASK-23.3 (dep TASK-23.2) - converge infrastructure/resilience/retry/dynamodb_store.py, then delete integrations/aws/{dynamodb_next,client_next,identity_store_next}.py once consumer count is zero. This is the slice that makes AC#2 pass.

BEHAVIOR DELTAS the slices must own explicitly (this task is NOT purely behavior-neutral, contrary to its original framing):
(a) client_next.execute_api_call caught EVERY exception and returned OperationResult.permanent_error. classify_aws_error re-raises unmapped exceptions instead. That is the decided contract (outbound-clients.md: "a KeyError is a bug, not an outcome") and each slice needs a test asserting propagation.
(b) dynamodb_next.query() hardcodes keys=["Items"] + force_paginate=True, so its OperationResult.data is a LIST, while dynamodb_store.fetch_due/get_stats/get_dlq_entries all call result.data.get("Items")/.get("Count"). Those three paths are broken against the real dispatcher today and pass only because tests/unit/infrastructure/resilience/retry/conftest.py:104 fakes a dict. Calling the boto3 client directly restores the dict shape the code already expects - a fix, not a regression - and TASK-23.3 carries an AC requiring real-shape fakes.
(c) client_next's ERROR_CONFIG downgraded ConditionalCheckFailedException to a warning log for dynamodb put_item/update_item. After migration the consumer owns that logging decision; keep contention out of error-level logs so alarms do not fire on normal claim contention.

AC-TO-SLICE: AC#1 -> TASK-23.1 + TASK-23.3. AC#2 -> TASK-23.1 (Google dispatcher) + TASK-23.3 (AWS dispatcher). AC#3 -> TASK-23.2 + TASK-23.3. AC#4 -> all three Done.

SCOPE BOUNDARIES (re-verified this session, correcting the earlier plan text):
- get_google_api_command_parameters exists ONLY in integrations/google_workspace/google_service.py:238, i.e. the NON-_next generation with 16 live consumer files. It is TASK-25.1 scope and cannot be closed here; AC#2 was reworded accordingly.
- "Exactly one client construction path per vendor" also cannot close here: integrations/aws/client.py still hosts execute_aws_api_call (TASK-25.2), integrations/aws/dynamodb.py is a third, older generation with its own client_config (TASK-25.2.2), and integrations/aws/shield.py still constructs its own clients (TASK-25.5 - confirmed zero production consumers). AC#2 now asserts only the _next generation's removal.
- AWSShield is NOT touched here. The earlier claim in this task's own text that "AWSShield feeds remaining AWS services" was disproven on re-grep and is owned by TASK-25.5 as a pure deletion.

BLAST RADIUS / ROLLBACK: each slice is a single git revert. TASK-23.1 has zero production blast radius. TASK-23.2 and TASK-23.3 each touch one correctness-critical primitive whose failure mode is duplicate processing (idempotency) or duplicate/dropped retries (retry store) - both are covered by existing unit suites plus the moto-backed idempotency conformance suite. No terraform, CI or environment-variable changes in any slice; table names and item shapes are unchanged.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-29 21:12
---
Upstream dependency repointed from TASK-22 to its final subtask TASK-22.5 (the slice that actually deletes infrastructure/clients/). TASK-22's subtasks (22.1-22.5) wire consumers to the integrations/ modules AS THEY EXIST TODAY, including the _next.py twins. This task then renames those survivors to canonical names and re-migrates the same consumers — an intentional, conflict-free second touch in a later PR of the same sprint. Note the MaxMind handoff: TASK-22.1 leaves an OperationResult client coexisting beside the legacy tuple geolocate()/healthcheck() in integrations/maxmind; unifying those two shapes is TASK-25, not this task.
---

created: 2026-07-31 17:07
---
RESEQUENCED per decisions/sdk-typing.md (2026-07-31). Previously this task renamed the surviving _next twin to a canonical name after TASK-22.x wired consumers onto it - a second touch of every consumer. Under the resequenced plan, TASK-22.2/22.3/22.4 migrate their consumers DIRECTLY to canonical factory+classify, so there is no twin to rename. This task is now the DELETION of the _next dispatcher generation plus convergence of its remaining non-facade consumers (idempotency store, resilience retry store) onto the get_aws_client/classify_aws_error primitive established in TASK-22.2.

Dependency changed from TASK-22.5 to TASK-22.4 (the AWS + Google primitives exist after 22.4; deleting integrations/*_next does not require the facade-tree deletion in 22.5, so this can run in parallel with 22.5). AC#2 retargeted from "each vendor has exactly one client construction path" to also assert the generic dispatchers + docstring scraper are gone. AC#3 retargeted from "all consumers import the canonical module" to explicitly name the idempotency/resilience convergence. AWSShield deletion stays in TASK-25 (it feeds the remaining AWS services).
---

created: 2026-07-31 18:49
---
Correction (2026-07-31): AC#2's wording was over-broad - it implied ALL execute_aws_api_call/execute_google_api_call occurrences disappear once this task is Done, but this task's own inventory only ever covered the _next-suffixed generation. Repo-wide grep (done while verifying AWS/Google client-migration task coverage) found a separate, non-_next execute_aws_api_call (integrations/aws/client.py, ~9 services/14 consumer files) and execute_google_api_call (integrations/google_workspace/google_service.py, 6 surfaces/16 consumer files) generation, each with far more live consumers than the _next twins. Those are now tracked as TASK-25.2 (AWS remainder) and TASK-25.1 (Google remainder) respectively. AC#2 reworded to scope explicitly to the _next generation and cross-reference the sibling tasks rather than silently over-promising.
---

created: 2026-08-31 17:37
---
DECOMPOSED 2026-08-31 (human-approved). TASK-23 tripped the single-PR size gate and is now a coordinator over TASK-23.1 / 23.2 / 23.3. Three corrections to earlier task text, all from fresh grep rather than the prior plan's prose:

1. AC#2's get_google_api_command_parameters clause was unachievable here: the docstring scraper exists only in integrations/google_workspace/google_service.py:238 (the non-_next generation, 16 live consumers, TASK-25.1 scope). google_service_next.py has no scraper. Same for "exactly one client construction path per vendor" - integrations/aws/{client.py, dynamodb.py, shield.py} all still construct clients after this task (TASK-25.2 / 25.2.2 / 25.5). AC#2 reworded to assert only the _next generation's dispatchers are gone.

2. AC#3's "behavior-neutral OperationResult outcomes" was inaccurate. The stores do not return OperationResult to their callers, and there are two real deltas: unmapped SDK exceptions now propagate instead of being swallowed into permanent_error (the decided contract), and dynamodb_next.query() returns a LIST (force_paginate + keys=["Items"]) while dynamodb_store.fetch_due / get_stats / get_dlq_entries all call result.data.get("Items")/.get("Count"). Those three paths are broken against the real dispatcher today and pass only because the unit conftest fakes a dict; calling boto3 directly fixes them. TASK-23.3 carries an AC requiring real-shape response fakes.

3. Consumer inventory confirmed much smaller than the original description implied: identity_store_next.py and all three Google _next modules have ZERO production consumers, so only two files (idempotency/dynamodb.py, resilience/retry/dynamodb_store.py) actually need migrating; everything else is deletion.
---
<!-- COMMENTS:END -->
