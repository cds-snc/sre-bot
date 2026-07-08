---
id: TASK-5
title: >-
  Rewrite idempotency store as atomic conditional claim behind an
  IdempotencyStore Protocol with in-memory fake
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:56'
labels:
  - security
  - phase-0
  - reliability
milestone: m-0
dependencies: []
references:
  - decisions/reliability.md
  - decisions/cloud-portability.md
  - claude-research-outcome.md
  - 'https://github.com/cds-snc/sre-bot/issues/1259'
priority: high
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/reliability.md (Idempotency) - the highest-priority correctness fix. Today app/infrastructure/idempotency/dynamodb.py does get() (get_item, line 47) then set() (plain put_item, lines 89-111) with no ConditionExpression - a TOCTOU race: two replicas both miss and both execute the mutation (SEC-4). key_builder.py:49 hashes the payload with sha256 truncated to 16 hex chars - payload hashes and truncation are both prohibited.

Build the capability-shaped Protocol (per claude-research-outcome.md):

    class IdempotencyStore(Protocol):
        def claim(self, key: str, ttl: timedelta) -> ClaimResult: ...  # NEW / COMPLETED / IN_PROGRESS
        def complete(self, key: str, outcome) -> None: ...
        def release(self, key: str) -> None: ...

Steps:
1. Define the Protocol + ClaimResult in app/infrastructure/idempotency/protocol.py. No DynamoDB vocabulary (no ConditionExpression parameters) in the Protocol surface.
2. DynamoDB implementation: claim = PutItem with ConditionExpression attribute_not_exists(pk), status IN_PROGRESS, bounded in-progress TTL. ConditionalCheckFailed branches: COMPLETED -> return recorded outcome; IN_PROGRESS unexpired -> concurrent duplicate; IN_PROGRESS expired -> take over and re-execute. complete() records the outcome; release() deletes so redelivery retries.
3. Key format <feature>:<intent>:<idempotency_id> where idempotency_id is a sender-assigned id stable across redeliveries (Slack event_id, webhook delivery id). Never request_id, never payload hashes, no truncation.
4. In-memory fake implementing the same Protocol, used by the integration tests (this is the standing second provider per decisions/cloud-portability.md contract 4).
5. Migrate existing callers of the old store; delete the get-then-put path and the payload-hash key builder.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 IdempotencyStore Protocol exists with claim/complete/release; no vendor types or vendor query syntax in its signatures
- [ ] #2 DynamoDB implementation uses ConditionExpression attribute_not_exists on claim; grep shows no get-then-put pattern remains in app/infrastructure/idempotency/
- [ ] #3 Concurrency test: two concurrent identical claims yield exactly one NEW and one IN_PROGRESS/COMPLETED outcome (asserted via the conditional-write path, not timing)
- [ ] #4 In-memory fake passes the same Protocol test suite as the DynamoDB implementation
- [ ] #5 Keys follow <feature>:<intent>:<idempotency_id>; no payload hash, no truncation (test on key builder)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All callers migrated; old key builder and racy store deleted
- [ ] #2 Tests pass including the shared Protocol conformance suite run against both implementations
- [ ] #3 PR references SEC-4 and decisions/reliability.md
<!-- DOD:END -->
