---
id: TASK-103
title: Make RecordStore.put_if_not_exists replay-safe against its own SDK retry
status: In Progress
assignee: []
created_date: '2026-09-17 20:40'
updated_date: '2026-10-15 20:14'
labels:
  - infrastructure
  - reliability
  - phase-4
milestone: m-4
dependencies:
  - TASK-25.2.5.4
  - TASK-27.4
references:
  - app/infrastructure/records/service.py
  - decisions/plugin-architecture.md
  - decisions/reliability.md
  - app/contracts/records/store.py
  - app/infrastructure/records/in_memory.py
  - app/infrastructure/coordination/dynamodb.py
priority: low
ordinal: 231000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make RecordStore.put_if_not_exists replay-safe against botocore's own retry. The method issues a conditional PutItem on a retrying client (app/integrations/aws/client.py: standard mode, 3 retries). If the first attempt lands but its response is lost, botocore resends the identical body, the condition now fails, and the caller is told the key already existed when it had just created it.

The first consumers are TASK-145.7 (IncidentStore.create) and TASK-145.5.6 (status-update store over put_if_not_exists); both wait on this task. Candidates later: TASK-37.1 WebhookStore, TASK-83.2.

Fix shape (settled in planning 2026-10-15): the DynamoDB store stamps an opaque per-call write token into the item, requests ReturnValuesOnConditionCheckFailure=ALL_OLD, and treats a failed condition whose returned item carries its own token as created. The token is stripped from every read and kept off the Protocol (decisions/reliability.md fourth branch; app/infrastructure/coordination/dynamodb.py is the prior art). History: filed 2026-09-17 while planning TASK-25.2.5.4; the storage service was renamed RecordStore by TASK-27.4.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 put_if_not_exists reports the item created (data=True) when the existing item carries this call's own write token, i.e. the call's own SDK-retried write; an item written by another call or without a token still reports data=False and is left unchanged
- [x] #2 The write token never reaches callers: get, query and update return exactly the written attributes; both stores reject an item using a reserved _rs_ attribute name with ValueError; the RecordStore Protocol signatures are unchanged
- [x] #3 botocore Stubber unit tests pin the request (token attribute, condition, ReturnValuesOnConditionCheckFailure=ALL_OLD) and the own-replay, foreign-item, missing-Item and other-error outcomes at the level of the coordination ownership tests; the store conformance suite covers the hidden token and reserved names on the in-memory and moto stores
- [x] #4 Task notes record that the method has no production caller on this branch and ships ahead of its consumers because TASK-145.7 and TASK-145.5.6 wait on it, plus the extra-attribute layout note for TASK-145.5.6
- [x] #5 ruff, mypy (no errors in touched files) and pytest tests --ignore=tests/smoke pass with output recorded
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-10-15 on branch feat/task-103-replay-safe-put, cut from up-to-date main (side PR R5, doc-11 work queue row 2; gates TASK-145.7). Stack K layers are not in this branch and are not planned against.

## Discovered state (grounded in code)
- Contract: app/contracts/records/store.py:219 `put_if_not_exists(table, item) -> OperationResult` (data=True created, data=False exists). Helpers `resolve_query_key` (:110) and `validate_record_update` (:157) live beside it; exports in app/contracts/records/__init__.py.
- DynamoDB: app/infrastructure/records/service.py:205-249. One conditional PutItem (`attribute_not_exists(#pk)`), no ReturnValuesOnConditionCheckFailure; ConditionalCheckFailedException maps to data=False (:240). Reads go through `_deserialize_item` (:59), the single choke point for get (:381), query (:435) and update's ALL_NEW (:333). `update()` already uses ReturnValuesOnConditionCheckFailure=ALL_OLD and reads `exc.response["Item"]` (:319-327): prior art inside this class.
- In-memory: app/infrastructure/records/in_memory.py:99-108; no SDK, so no replay; needs only reserved-name parity.
- Client: app/integrations/aws/client.py:158-165 builds every client with `retries={"mode": settings.RETRY_MODE, "max_attempts": 3}` (app/integrations/aws/settings.py:42-47, default mode "standard"), so a lost response on PutItem is resent. get_record_store (service.py:445) uses get_aws_client("dynamodb") with retries on.
- Prior art 1, claim token: app/infrastructure/coordination/dynamodb.py:51-137 (uuid4 hex written into the item, matched on the re-read; decisions/reliability.md:18 "fourth branch": opaque per-call owner token, kept off the Protocol).
- Prior art 2, content equality: app/features/incident/core/adapters/status_updates.py:104-115 resolves the same replay by comparing the ALL_OLD item to the item written. Not reused: DynamoDB renormalises numbers on store (Decimal 1.0 stored as 1), so equality can miss a genuine replay, and equal-content writers from two callers are indistinguishable.

## Callers of put_if_not_exists (rg over repo, 2026-10-15)
Production callers on this branch: none.
Tests: app/tests/unit/infrastructure/records/test_records_dynamodb_store_operations.py:95,112,121,134,368 (MagicMock client; the bare ClientError cases still pass, see step 6); app/tests/unit/infrastructure/records/test_records_in_memory_store_operations.py:35; app/tests/integration/infrastructure/records/test_records_store_query_conformance.py:71,77,79,86,88 (moto and in-memory); app/tests/unit/contracts/records/test_records_query_spec.py:111 (signature pin, must stay `["self","table","item"]`).
Future callers that depend on this: TASK-145.7 (IncidentStore.create, step 1 of its plan, conditional put on the incident id) and TASK-145.5.6 (status-update store rebuilt over put_if_not_exists, replacing the equality check in adapters/status_updates.py:111). TASK-83.2 and TASK-37.1 are further candidates. TASK-145.8 and TASK-145.5.7 use update, which is not changed here.
Effect: no behavior change for any caller today. AC#3 as filed (defer if no caller) is stale: the first consumers are downstream tasks that wait on this one (decisions/plugin-architecture.md Path A is respected: the surface is the existing method, no new operation is added ahead of need).

## Decision
The store stamps every put_if_not_exists with an opaque per-call write token inside the item, asks DynamoDB to return the existing item on a failed condition (ReturnValuesOnConditionCheckFailure=ALL_OLD), and answers data=True when the returned item carries this call's token. No second read, so no new read-failure mode. The token is invisible to callers: stripped in `_deserialize_item`, so get, query and update results equal what the caller wrote. It stays off the RecordStore Protocol (cloud-portability rule 4): signatures unchanged; portable to Redis (SET NX value), Postgres (owner column), Cosmos (owner field).
Rejected: (a) content equality as in status_updates.py (above); (b) a second ConsistentRead get as in the coordination store (extra round trip and a read-failure branch, ALL_OLD already carries the item atomically); (c) TransactWriteItems with ClientRequestToken (DynamoDB-specific, different error shape, double WCU); (d) a retries=False client for writes (loses throttle resilience).
Reserved names: attribute names starting with `_rs_` are reserved by the store; the token attribute is `_rs_write_token`. Both stores reject an item that uses a reserved name in put and put_if_not_exists with ValueError (same style as validate_record_update), so the fake stays faithful.

## Steps
1. app/contracts/records/store.py + __init__.py: add `RESERVED_ATTRIBUTE_PREFIX = "_rs_"` and `validate_record_item(item)` (raises ValueError naming the offending attribute); export both. Extend the RecordStore docstring: put_if_not_exists returns data=True only for the call that created the item even when the SDK retried it; names under the reserved prefix are rejected. Protocol signatures untouched. (~25 LOC)
2. app/infrastructure/records/service.py: add `_WRITE_TOKEN_ATTRIBUTE = "_rs_write_token"` and `_new_write_token()` (uuid4 hex, a seam for tests); `_deserialize_item` drops the token attribute; `put` and `put_if_not_exists` call `validate_record_item`. (~15 LOC)
3. service.py `put_if_not_exists`: serialize the item plus token; pass `ReturnValuesOnConditionCheckFailure="ALL_OLD"`; on ConditionalCheckFailedException read `exc.response.get("Item")`: token equal to ours returns success(data=True, message="Item created") and logs `records_put_if_not_exists_replay_resolved` at info; a different or missing token, or no Item in the response, returns success(data=False, "Item already exists"). Other classified errors keep the current error result. Catch ClientError and BotoCoreError separately as `update()` does, so the response is reachable. (~35 LOC)
4. service.py logging for put_if_not_exists (touched events): add `operation="put_if_not_exists"` and `key` (the item's key attribute values, never the payload or the token) to the created, already-exists, replay-resolved and error events. Same for the `put` error event only if touched for step 2. No secrets.
5. app/infrastructure/records/in_memory.py: call `validate_record_item` in put and put_if_not_exists (no token: nothing replays). (~4 LOC)
6. Tests (below). Existing MagicMock cases in test_records_dynamodb_store_operations.py keep passing (a ClientError without Item resolves to data=False); `test_uses_condition_expression` gains an assertion on the new keyword. Fix any simple bug or deprecated construct met in the touched functions; none found at planning time.
7. Task notes (CLI): record that the method has no production caller on this branch and ships first because TASK-145.7 and TASK-145.5.6 wait on it, and the physical layout note (every put_if_not_exists item carries one extra attribute, ~45 bytes) for TASK-145.5.6's "item layout unchanged" criterion.

## Size and gate
~80 production LOC across 4 files (store.py, __init__.py, service.py, in_memory.py), one subsystem (records contract and its two implementations); tests ~220 LOC across 4 files. Under ~400 LOC and ~10 files; no refactor mixed with behavior; one `git revert` restores the old behavior (no callers, no schema or terraform change). Gate: pass, no decomposition.

## AC traceability
AC#1 (own retried write reports created; foreign item reports exists) -> steps 2-3 -> tests 1, 2, 3 below.
AC#2 (token invisible, reserved names rejected, signatures unchanged) -> steps 1, 2, 5 -> tests 4, 5, 6, 7, 8.
AC#3 (Stubber-level request/replay tests plus store conformance) -> step 6 -> every test below.
AC#4 (ship-ahead rationale recorded) -> step 7.
AC#5 (gates) -> run ruff, mypy scoped to touched files, pytest, record output.
Every step maps to an AC (step 4 is the logging rule for touched events, enabling AC#3 diagnostics).

## Test matrix
New app/tests/unit/infrastructure/records/test_records_dynamodb_store_replay.py (botocore Stubber on a real boto3 client with dummy credentials, as in tests/unit/infrastructure/coordination/test_coordination_dynamodb_ownership.py; token fixed via monkeypatching `_new_write_token`):
1. Happy: first attempt succeeds; expected params pin Item with the token attribute, ConditionExpression and ReturnValuesOnConditionCheckFailure=ALL_OLD; data=True.
2. Replay (idempotency): condition fails with modeled `Item` bearing our token; data=True.
3. Competitor: condition fails with `Item` bearing another token; data=False. Same for an item with no token (legacy or `put`-written).
4. Failure: ConditionalCheckFailed without `Item` in the response -> data=False; AccessDenied and a connection error -> error result, status and error_code classified, no exception.
5. Boundary: sort-key table pins the condition on the partition attribute only (full key identity unchanged); item with None values still serializes without nulls.
Edit in place app/tests/unit/infrastructure/records/test_records_dynamodb_store_operations.py: token stripped from get, from query items and from update's returned item; put and put_if_not_exists reject a reserved attribute with ValueError and make no client call.
New app/tests/unit/contracts/records/test_records_item_validation.py: validate_record_item accepts ordinary and underscore-leading names, rejects the reserved prefix.
Edit in place app/tests/integration/infrastructure/records/test_records_store_query_conformance.py, class TestPutIfNotExists (runs on the in-memory fake and moto): get after create equals the written item exactly; a query returns the item without extra attributes; a reserved attribute raises ValueError on both stores.
Unchanged and must pass: tests/unit/contracts/records/test_records_query_spec.py (signature pin), tests/unit/infrastructure/records/test_records_store_protocol_conformance.py, test_records_store_conformance_enrollment.py.
Docstrings describe behavior only.

## Assumptions and doubts (each with verification)
- Botocore resends the identical serialized body on retry, so the token and the condition are identical on replay. Basis: the same verification as TASK-25.2.5.4 (botocore/endpoint.py `_send_request`); standard mode retries transient errors RequestTimeout/ConnectionError/HTTPClientError and HTTP 500/502/503/504 for every operation with no idempotency check (https://docs.aws.amazon.com/boto3/latest/guide/retries.html; botocore/retries/standard.py `TransientRetryableChecker`, `_TRANSIENT_STATUS_CODES`); adaptive mode uses the same retry conditions; the repo default is standard, 3 retries (4 attempts), set in app/integrations/aws/client.py:158-165. ConditionalCheckFailedException is a 400, not retried, so the caller sees it only after the first landed. Verify: re-read `_send_request` after a botocore bump (`sed -n '/def _send_request/,/def _needs_retry/p' app/.venv/lib/python3.14/site-packages/botocore/endpoint.py`).
- A failed PutItem condition returns the stored item when ReturnValuesOnConditionCheckFailure=ALL_OLD (valid values NONE and ALL_OLD; https://docs.amazonaws.cn/amazondynamodb/latest/APIReference/API_PutItem.html; https://www.hackerone.com/blog/ensuring-robustness-dynamodb-operations-role-returnvaluesonconditioncheckfailure). The botocore model for ConditionalCheckFailedException has members `message` and `Item` (verified locally on botocore 1.42.54), and `update()` already reads `exc.response["Item"]`. Verify: the Stubber test with modeled_fields validates the shape; moto 5.2.2 handles the parameter for put_item (app/.venv/.../moto/dynamodb/responses.py:612) and the conformance suite exercises the plain path.
- The ALL_OLD item arrives unconverted AttributeValue dicts: deserialize with `_deserialize_item` before comparing, or compare the raw `{"S": ...}` form; verify in test 2.
- No extra IAM action is needed for ReturnValuesOnConditionCheckFailure on PutItem (the repo's update path already relies on it under the same grants). Verify: AWS DynamoDB IAM docs on dynamodb:PutItem; no terraform change planned.
- DynamoDB Local (AWS_ENDPOINT_URL for dev) supports the parameter; the same assumption already holds for update(). Verify: run the local compose smoke only if the human asks (smoke is excluded).
- Residual window: a replay arriving after another writer deleted or overwrote the item cannot be recognised (the token is gone) and reports exists, or recreates after a delete; the window is the SDK retry backoff and is inherent to any client-side check. Accepted; note in the method docstring.
- `put` (overwrite) does not stamp a token, so a put_if_not_exists replay after an intervening `put` reports exists. Same residual window.
- Legacy direct readers of tables written through this method (the legacy incident module, via boto) see one extra attribute and ignore it. Verify when TASK-145.5.8/145.7 land; flagged in the step 7 note.

## Blast radius and rollback
No production caller: runtime impact today is nil. If shipped wrong, the risk is to future callers only (a false "created" would double-create; a false "exists" is today's behavior). Items written by the new method carry one extra attribute; reverting the PR leaves that attribute on already-written items, which the old code returns from get/query (harmless extra key) and which nothing reads; a revert is otherwise complete and safe. Ordering: this must merge before TASK-145.7 and TASK-145.5.6 call the method; no env var, terraform or manifest prerequisite.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented TDD on feat/task-103-replay-safe-put (side PR R5, doc-11 Work queue row 2). Tests were written first and failed on ImportError, missing token and missing validation; then minimal code, then green.

Why it ships now: put_if_not_exists has no production caller on this branch. It ships ahead of its consumers because TASK-145.7 (IncidentStore.create) and TASK-145.5.6 (status-update store) wait on it.

Layout note for TASK-145.5.6: every item written through put_if_not_exists carries one extra attribute, _rs_write_token (a uuid4 hex, about 45 bytes). Every read strips it (get, query and update return exactly the caller's attributes). Two concurrent writers of identical content now get one created and one already-exists; today's equality check in adapters/status_updates.py reports both as success. Comments on 145.5.6 and 145.7 say so.

Production changes (4 files, +100/-25):
- contracts/records/store.py and __init__.py: RESERVED_ATTRIBUTE_PREFIX ("_rs_") and validate_record_item(item), both exported. validate_record_update also refuses a change or guard on a reserved name, so the token cannot be forged through update; this is an addition to the plan, about 2 lines. The RecordStore docstring states the put_if_not_exists replay guarantee and the reserved prefix. Protocol signatures are unchanged (test_records_query_spec pin passes).
- infrastructure/records/service.py: put_if_not_exists writes a per-call token (seam _new_write_token) and sends ReturnValuesOnConditionCheckFailure=ALL_OLD.
  - On ConditionalCheckFailedException, an old item carrying this call's token returns data=True and logs records_put_if_not_exists_replay_resolved at info. Another token, no token or no Item returns data=False.
  - ClientError and BotoCoreError are handled separately, as update() does.
  - _deserialize_item drops the token. put and put_if_not_exists call validate_record_item.
  - The touched log events carry operation and key (the key attributes only, never the payload or the token).
  - The constant is named _WRITER_ATTRIBUTE because ruff S105 flags "TOKEN" in a constant name as a password (false positive; renamed, not suppressed).
  - _stored_writer reads the modeled Item through a cast, since botocore's typed ClientError response does not declare it (no type: ignore).
- infrastructure/records/in_memory.py: put and put_if_not_exists call validate_record_item (no token, since nothing replays in the fake).

Tests:
- New tests/unit/infrastructure/records/test_records_dynamodb_store_replay.py: botocore Stubber on a real client. Covers the first write (pins the token attribute, the condition and ALL_OLD), the own replay, another writer's token, no token, no Item, AccessDenied, a connection failure, and a fresh token per call.
- New tests/unit/contracts/records/test_records_item_validation.py.
- Edited in place:
  - test_records_dynamodb_store_operations.py: the condition test pins ALL_OLD and the token; get, query and update strip the token; a reserved name is refused before any call.
  - test_records_store_query_conformance.py (in-memory and moto): a created item reads back exactly as written; a reserved name is refused.
  - test_records_contracts_imports.py: export pin.

Residual window, accepted in the plan and stated in the docstring: a replay that meets an item another writer replaced or deleted in between reports that it existed.

Merge note: the comments on TASK-145.5.6 and TASK-145.7 are appended on this branch; Stack K layers also edit task-145.7, so expect a possible backlog-file conflict when the second of the two merges (resolve by keeping both).

Gates (from app/):
- uv run ruff check . -> All checks passed!
- uv run ruff format --check (touched files) -> 9 files already formatted
- uv run lint-imports -> Contracts: 12 kept, 0 broken.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 48 errors in 19 files (checked 411 source files); 0 in touched files (pre-existing)
- uv run pytest tests --ignore=tests/smoke -> 5022 passed in 107.90s
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:11
---
2026-09-24 citation fix: decisions/layers.md, capability-packages.md and events.md were deleted and replaced by decisions/plugin-architecture.md (six layers: server, features, capabilities, infrastructure, integrations, contracts). Read those references in this task as plugin-architecture.md. Path A infrastructure capabilities are now split: hosting contracts (storage, coordination, queue, secrets) live in app/contracts/ with implementations in app/infrastructure/; workplace systems and shared business engines live in app/capabilities/. Path B adapters are unchanged (outbound-clients.md). put_if_not_exists is on the StorageService contract, which moves to app/contracts/ (TASK-108); the replay-safety fix lands with its first consumer as planned.
---

created: 2026-10-15 20:07
---
Plan approved by the human 2026-10-15 with decisions: (1) a per-call write token (_rs_write_token) resolves the SDK replay, not content equality; (2) comments on TASK-145.5.6 and TASK-145.7 note the extra attribute and the stricter concurrent-writer outcome; (3) the reserved _rs_ prefix is enforced in both stores through validate_record_item in the contract; (4) Stubber-level replay tests are the accepted depth (no end-to-end lost-response test).
---
<!-- COMMENTS:END -->
