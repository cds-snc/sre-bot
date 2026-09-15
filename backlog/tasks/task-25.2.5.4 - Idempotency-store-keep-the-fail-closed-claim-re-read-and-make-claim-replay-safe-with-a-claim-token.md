---
id: TASK-25.2.5.4
title: >-
  Idempotency store: keep the fail-closed claim re-read and make claim
  replay-safe with a claim token
status: To Do
assignee: []
created_date: '2026-09-15 20:09'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - app/infrastructure/idempotency/dynamodb.py
  - app/infrastructure/idempotency/lease.py
  - app/tests/unit/infrastructure/idempotency/test_dynamodb_store.py
  - app/tests/integration/infrastructure/idempotency
parent_task_id: TASK-25.2.5
priority: high
ordinal: 217000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-25.2.5. Independent of .1-.3: the store already uses get_aws_client/classify_aws_error directly (TASK-23.2) and does not use the adapter.

(a) Keep the re-read downgrade (human decision 2026-09-15). In infrastructure/idempotency/dynamodb.py:88-95, a classified SDK failure while re-reading a contended claim returns ClaimResult.IN_PROGRESS. The only production users are leases (infrastructure/idempotency/lease.py, used by the jobs/scheduled_tasks.py singleton jobs and packages/access/sync/platform_lock.py). Returning IN_PROGRESS there fails closed: the run is skipped rather than risking two holders. Put the reason in the claim() docstring and add the unit test, which does not exist today.

(b) Self-replay (human decision 2026-09-15). claim()'s conditional put_item runs on the retrying client. If the first attempt succeeds but its response is lost (timeout or 5xx), the SDK resends. The condition then fails, and the re-read finds our own IN_PROGRESS record, so claim() returns IN_PROGRESS. The lease stays held by nobody until IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS expires. Fix: write a per-call claim_token (uuid4 hex) into the item. On ConditionalCheckFailedException, return NEW if the re-read item is IN_PROGRESS with the same token. The SDK resends the identical request, so the token matches only our own replay. The Protocol, the in-memory store (no SDK replay) and complete/release (replay-safe) are unchanged.

Tests: extend tests/unit/infrastructure/idempotency/test_dynamodb_store.py in its existing MagicMock-client style. The moto conformance suite under tests/integration/infrastructure/idempotency must pass unchanged.

Overlap: TASK-58 later renames this module with identical behaviour; nothing here conflicts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A classified failure of the ConsistentRead after a contended claim still returns IN_PROGRESS; the claim() docstring records the fail-closed lease rationale and a unit test pins the behaviour
- [ ] #2 claim() writes a per-call claim_token; when the conditional put fails and the re-read item is IN_PROGRESS with the same token it returns NEW, and with a different or missing token it returns IN_PROGRESS; both cases have unit tests
- [ ] #3 The moto conformance suite under tests/integration/infrastructure/idempotency passes unchanged; the IdempotencyStore Protocol, the in-memory store, complete() and release() are unchanged
- [ ] #4 Both decisions are recorded in TASK-25.2.5 notes; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded
<!-- AC:END -->
