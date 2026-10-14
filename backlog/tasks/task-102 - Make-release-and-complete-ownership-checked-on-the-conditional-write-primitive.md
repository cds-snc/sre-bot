---
id: TASK-102
title: Make release and complete ownership-checked on the conditional-write primitive
status: Done
assignee: []
created_date: '2026-09-17 20:40'
updated_date: '2026-10-14 19:36'
labels:
  - infrastructure
  - reliability
  - phase-4
milestone: m-4
dependencies:
  - TASK-25.2.5.4
references:
  - decisions/reliability.md
  - app/infrastructure/idempotency/dynamodb.py
  - app/infrastructure/idempotency/protocol.py
  - decisions/cloud-portability.md
priority: medium
ordinal: 230000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while planning TASK-25.2.5.4 on 2026-09-17; human decision the same day to file it rather than fold it in, because the fix needs a Protocol change and TASK-25.2.5.4's AC#3 freezes the Protocol.

THE HAZARD. release() and complete() (app/infrastructure/idempotency/dynamodb.py:110-140) write unconditionally: delete_item by key, put_item by key. A claimant whose in-progress TTL elapsed mid-run - a paused process, a long job, a GC stall - has already had its record taken over by a second holder under the expired-claim takeover branch. When the first claimant finishes, its release() deletes the SECOND holder's live record, or its complete() overwrites it. The lease is then free while a run is still in flight, and a third claimant can start.

This is NOT the hazard TASK-25.2.5.4 fixes. That one is mistaken identity on a re-read ("did I write this record, or did someone else"), which a random per-call owner token answers completely. This one is staleness and ordering ("is my grant still the newest one"), which a random token does not answer. Martin Kleppmann's fencing-token argument is about exactly this distinction, and Redis's own distributed-locking documentation now concedes the point: "You should implement fencing tokens. This is especially important for processes that can take significant time... don't assume that a lock is retained as long as the process that had acquired it is alive." (reviewed 2026-09-17).

WHY IT NEEDS A PROTOCOL CHANGE. The token is generated inside claim() and is a local variable. To gate release/complete on it, the caller must carry it back, so it has to surface on ClaimOutcome or on the release/complete signatures.

SEQUENCING (read this before wiring more dependencies). TASK-58 cuts the same surface - it renames the primitive to ConditionalWriteStore and splits idempotency and lease facades over it. Either order works and NEITHER is wired as a dependency, deliberately:
- This task first: TASK-58's rename then carries the already-correct Protocol along, which is mechanical.
- TASK-58 first: this task lands on the new shape and touches the facades directly.
Do NOT gate this task on TASK-58. TASK-100 (the fail-open flip) depends on THIS task, because fail-open without an ownership check actively creates the cascade described above - a caller that is told NEW when it does not hold the lease will release another holder's record. Gating this on the full ConditionalWriteStore rename would therefore push a correctness fix behind a rename. Whoever picks this up should check TASK-58's status and coordinate, not wait.

HONEST CAVEAT FOR THE PLANNER. True fencing requires the PROTECTED RESOURCE to reject stale tokens, which is not available here: the resources are Slack, Google Workspace and AWS Identity Center. What is achievable is the narrower and still worthwhile guarantee that a stale holder cannot destroy a live holder's record - a conditional delete/put on the owner token. Duplicate execution itself remains tolerated per decisions/reliability.md and is TASK-99's concern, not this one. Do not scope this as "make leases exactly-once".

Portability was checked 2026-09-17: an owner token compared on release is the canonical form in Redis (SET NX PX plus compare-and-delete), expressible in Postgres (unique insert with an owner column, conditional DELETE) and in Cosmos (etag, or an explicit owner field). It does not strand the design on DynamoDB.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A claimant whose claim was taken over after its in-progress TTL elapsed cannot delete or overwrite the new holder's record, and no release can delete a COMPLETED record
- [x] #2 The ownership token travels from claim to release/complete through the Protocol rather than through implementation-local state; release/complete return False when ownership was lost, and infrastructure failures still raise
- [x] #3 The in-memory implementation enforces the same ownership rule, so the conformance suite covers both
- [x] #4 The limits are written down: this prevents a stale holder destroying a live claim; it does not make lease-protected execution exactly-once
- [x] #5 Every caller of release/complete (Access Sync locks and Tier-2 leases) carries the claim token
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SCOPE AND SEQUENCING
Layer 1 of stack C (TASK-102 -> TASK-58). Stays on today's paths (app/infrastructure/idempotency/); TASK-58's rename then carries the ownership-checked Protocol along mechanically. Out of scope: the rename, facade split, read-failure policy (TASK-58/TASK-100), duplicate-safe job bodies (TASK-99), true fencing. TASK-6 is Done; TASK-64 (moves run_if_leased) and TASK-65 (deletes _tier2) are To Do and unaffected because run_if_leased keeps its signature and owns the token internally.

DESIGN DECISIONS
D1. The token surfaces on ClaimOutcome as claim_token: str | None (set exactly when result is NEW, None otherwise). release and complete take it as a required parameter: release(key, claim_token) -> bool and complete(key, outcome, claim_token) -> bool. Required, no default, so no caller can silently skip the check. The token is an opaque string; the Protocol says nothing about how it is stored.
D2. Ownership lost = no exception, no write, return False (True when applied), plus a structured warning log (claim_ownership_lost, key and operation, never the token). Raising would turn a release in a finally block into an exception that masks the job's own error. Infrastructure failures (throttling, network) still raise RuntimeError exactly as today. Callers may ignore the bool; none of today's callers need to branch on it.
D3. DynamoDB adapter stays on its own boto3 calls (put_item, delete_item). RecordStore is not used: its update never creates and cannot delete, it speaks the RecordTable key layout rather than this table's schema, and the claim's expiry-takeover condition is not an equality guard. Moving would be a data migration and a different contract; reliability.md keeps the conditional write as its own coordination contract. The adapter uses ConditionExpression on the stored claim_token attribute only.
D4. DynamoDB conditions. complete: put_item with ConditionExpression claim_token = :token, and the COMPLETED item keeps claim_token. Not conditioned on status, so a botocore replay of a complete whose first attempt already landed still matches and stays True. release: delete_item with claim_token = :token AND status = :in_progress, so a stale or replayed release can never delete a COMPLETED record (a bug today: release deletes any record). A release replay after a successful first delete finds nothing and reports False with a warning; this is benign and documented. An expired-but-not-taken-over record can still be released or completed by its owner (token still matches). An absent record (TTL purge) counts as ownership lost.
D5. Keep the claim path unchanged except returning the already-generated claim_token in every NEW outcome, including the own-replay branch. The token is not persisted anywhere outside the store. In particular it is NOT written into the Access Sync holder record in JobStatusStore, which pollers can read.
D6. In-memory store enforces the same rules under its lock: record carries a uuid4 hex token, release requires token match and status IN_PROGRESS, complete requires token match, both return False otherwise.
D7. Lease helpers: acquire_lease(store, name) -> str | None (the claim token on a win, None otherwise); release_lease(store, name, claim_token) -> bool; run_if_leased holds the token locally and its signature is unchanged. Access Sync: acquire_lock returns str | None; the token is threaded ingress -> spawn_*_sync_thread kwargs -> run_*_sync_job -> release_lock(key, lock_store, claim_token). The two-step acquire-in-request, release-in-background-thread shape is why the token must travel as an argument.

CALL SITES (every release/complete caller migrated)
- app/infrastructure/idempotency/protocol.py:15-18 (ClaimOutcome), :29-46 (Protocol methods)
- app/infrastructure/idempotency/dynamodb.py:60-115 (claim returns token), :110-140 (complete, release)
- app/infrastructure/idempotency/in_memory.py:21-76
- app/infrastructure/idempotency/lease.py:13-41 (acquire_lease, release_lease, run_if_leased)
- app/infrastructure/idempotency/__init__.py:12-24 docstring usage example (complete signature)
- app/packages/access/sync/platform_lock.py:15-41 (acquire_lock, release_lock)
- app/packages/access/sync/interactions/ingress.py:91-115 and :172-196 (acquire_lock result passed on to the spawn calls)
- app/packages/access/sync/job_runner.py:55-134, :137-239, :247-290, :293-330 (run_* and spawn_* take and forward claim_token; release_lock at :134 and :239)
- app/jobs/scheduled_tasks.py:84-87 uses run_if_leased only: no change.
- Nothing else in app/ calls claim/complete/release (get_idempotency_store has no production caller). bin/unlock-sync-job.sh deletes records directly as an operator override and is deliberately unchanged.
- pyproject.toml import-linter ignore entries name infrastructure.idempotency, which does not move: no edit.

STEPS (TDD: tests first, then minimal code)
1. Conformance tests (AC1, AC3). Extend app/tests/integration/infrastructure/idempotency/test_idempotency_store_conformance.py, which already runs through the idempotency_store fixtures that the enrollment test (test_idempotency_store_conformance_enrollment.py, from TASK-27.3) ties to every concrete subclass. No new fixture mapping is needed: in-memory and moto-DynamoDB both run every case, and make check-fake-coverage stays green because InMemoryIdempotencyStore keeps explicitly subclassing the Protocol. Add a store_clock fixture in the suite's conftest.py that replaces the time name in the dynamodb and in_memory modules so expiry is deterministic without sleeping. Cases: owner release then reclaim is NEW; owner complete then claim is COMPLETED with the outcome; stale holder (A claims, clock passes TTL, B takes over) release returns False and B's record survives (a third claim is IN_PROGRESS); stale holder complete returns False and does not overwrite B's record; B then releases with its own token and the key is claimable; wrong or unknown token release and complete return False; release on a COMPLETED record returns False and the outcome survives; release on a never-claimed key returns False; complete replayed with the same token stays True; non-NEW claim outcomes carry claim_token None; NEW outcomes carry distinct tokens per claim.
2. DynamoDB unit tests (AC1), new file app/tests/unit/infrastructure/idempotency/test_idempotency_dynamodb_ownership.py using botocore Stubber: exact put_item and delete_item ConditionExpression and attribute values; ConditionalCheckFailedException maps to False with the warning logged; throttling or another ClientError raises RuntimeError; unclassified error propagates; claim returns the written token on both NEW branches. Update existing test_dynamodb_store.py (complete :180, release :194) and test_in_memory_store.py (:62-83) for the new signatures in place; they keep their current style.
3. Protocol shape tests (AC2): update tests/unit/infrastructure/idempotency/test_idempotency_store_protocol.py (FakeIdempotencyStore, signature assertions :53-61, ClaimOutcome tests): claim_token defaults to None, release and complete require claim_token, return annotations are bool.
4. protocol.py: add claim_token to ClaimOutcome; change release and complete signatures and docstrings (docstring states the ownership contract and the False meaning). Token documented as opaque and backend-neutral.
5. dynamodb.py then in_memory.py per D4, D5 and D6. In the DynamoDB methods call classify_aws_error first to get the code, then branch on ConditionalCheckFailedException. Also update the claim() docstring sentence saying the token stays off the Protocol: it is now on ClaimOutcome for ownership and still not matched in the claim condition.
6. lease.py per D7, plus the __init__.py docstring example. Update tests/unit/infrastructure/idempotency/test_lease.py (acquire returns token or None, release with token, run_if_leased never releases a lease taken over mid-run).
7. Access Sync consumers per D7 (platform_lock, ingress, job_runner). Update tests in place: tests/unit/packages/access/sync/test_platform_lock.py, test_job_runner.py (lock_store.release asserted with key and claim_token at 6 sites), test_access_sync_routes.py. Add a test that the holder record written to JobStatusStore does not contain the token.
8. Docs (AC4). decisions/reliability.md: (a) Idempotency paragraph (line 18): release and complete are conditional on the claim token, return False when ownership is lost; (b) Background jobs paragraph (line 30): a lease holder whose TTL elapsed cannot delete or overwrite the new holder's record; (c) the limits, stated plainly: this prevents a stale holder destroying a live claim; it is not fencing (the protected resources, Slack, Google Workspace and AWS Identity Center, do not check tokens), duplicate execution is still tolerated and is TASK-99's concern, a record purged by the TTL sweeper makes a late complete or release a no-op, and a replayed release can report False after succeeding; (d) a Decision log entry dated 2026-10-14. Note in cloud-portability.md only if it names the release/complete signatures (check; otherwise untouched).
9. Gates, from app/: ruff check, mypy (0 errors in touched files; repo-wide errors outside them are ignored), pytest tests --ignore=tests/smoke, make check-fake-coverage, lint-imports. Record command output in the notes.

AC TRACEABILITY
AC1: steps 1, 2, 5. AC2: steps 3, 4, 7 (conformance cases drive the token through the Protocol only). AC3: steps 1, 5 and the existing enrollment test; test run through both fixtures. AC4: step 8.

TEST MATRIX (happy / boundary / failure / authorization)
Happy: owner release and complete. Boundary: expired-but-untaken-over record still releasable by owner; completed record not releasable; replayed complete. Failure: infra error raises RuntimeError, unclassified error propagates. Authorization (ownership): stale holder, wrong token, unknown key.

SIZE AND GATE
Production: 8 files (protocol, dynamodb, in_memory, lease, __init__ docstring, platform_lock, ingress, job_runner) plus reliability.md, roughly 150-200 changed LOC. Two subsystems touched (infrastructure/idempotency and packages/access/sync consumers), at the limit but not over; the consumer migration cannot be split off because the Protocol change is a break. No rename mixed in. A single revert restores prior behavior; no data or schema change (claim_token attribute already written by claim). Verdict: passes the single-PR gate; no decomposition.

ASSUMPTIONS AND DOUBTS
- Assumes no production caller of complete exists outside tests (verify: rg for .complete( and idempotency_store usage; get_idempotency_store has none today).
- Assumes the DynamoDB COMPLETED/IN_PROGRESS items written before this deploy all carry claim_token (claim has written it since TASK-25.2.5.4); a record from before that has no token, so its stale holder's release becomes a no-op and the record expires by TTL. Verify the merge date of that change against the deploy; acceptable either way.
- Assumes patching the time name in both implementation modules is enough for a deterministic clock under moto (verify when writing the fixture).
- Existing test_dynamodb_store.py uses a MagicMock client rather than Stubber; left in that style for updated cases, new ownership tests use Stubber.

BLAST RADIUS AND ROLLBACK
Access Sync locks and the three Tier-2 scheduler leases are the only live consumers. A bug in the token plumbing would make release a no-op and leave locks held until the in-progress TTL expires (bounded by lock_stale_seconds and the lease TTL); a single revert restores service. No ordering constraint with config or infrastructure. TASK-58 inherits the new signatures and moves the conformance fixtures and enrollment test with the rename; TASK-100 builds on this.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented as planned (D1-D7), on today's paths so TASK-58 carries it along unchanged.

What changed
- protocol.py: ClaimOutcome.claim_token (set exactly on NEW); complete(key, outcome, claim_token) -> bool and release(key, claim_token) -> bool, token required.
- dynamodb.py: complete is a put conditional on #claim_token = :claim_token and keeps the token on the COMPLETED item (a replayed complete stays True); release is a delete conditional on the token AND status IN_PROGRESS (fixes release deleting a COMPLETED record). ConditionalCheckFailedException -> False plus a claim_ownership_lost warning (key, operation; never the token); other classified errors still raise RuntimeError, unclassified ones propagate. claim returns the token on both NEW branches.
- in_memory.py: same rules under its lock; claim simplified to one takeover path.
- lease.py: acquire_lease -> str | None, release_lease(store, name, claim_token) -> bool; run_if_leased signature unchanged.
- Access Sync: acquire_lock -> str | None; the token travels ingress -> spawn_*_sync_thread -> run_*_sync_job -> release_lock. It is not written into the holder record.
- decisions/reliability.md: ownership paragraph with the limits (no fencing, no exactly-once, TTL-purged record makes a late call a no-op, replayed release reports False), a Checks line, and a 2026-10-14 change entry. cloud-portability.md names no release/complete signature, so it is unchanged.

Deviation from the plan
- No store_clock fixture: the suite's existing expiring_idempotency_store fixture (in-progress TTL -1) gives deterministic takeover for both stores, and moto honours the conditional put and delete (verified in the first green run).

Tests
- Conformance (both stores): token on NEW only, distinct per claim; foreign-token release/complete refused; release never deletes COMPLETED; stale holder's release/complete after takeover refused and the new holder's record survives; owner can still release an expired claim nobody took over; replayed complete stays True.
- New unit files: tests/unit/infrastructure/idempotency/test_idempotency_dynamodb_ownership.py (Stubber: exact condition expressions, False mapping, error propagation, log without token) and tests/unit/packages/access/sync/test_access_sync_ingress_lock_token.py (the token handed to the spawned job owns the lock).
- Updated in place: protocol shape, DynamoDB, in-memory, lease (incl. a job overtaken mid-run does not free the new holder's lease), platform_lock (foreign token, holder record has no token), job_runner and routes. Removed the deprecated `from __future__ import annotations` from test_lease.py and test_platform_lock.py.
- First red run: 85 failures, all missing-feature errors (no claim_token attribute, old signatures).

Gates (2026-10-14, from app/)
- uv run ruff check . -> All checks passed!; ruff format --check -> 907 files already formatted
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 48 errors in 19 files; 0 in touched files (all pre-existing: i18n, modules/*, resilience, slack channels, incident adapters)
- uv run pytest tests --ignore=tests/smoke -> 4831 passed
- make check-fake-coverage -> OK: every covered Protocol has an in-memory fake (6 baselined gap(s) remain)
- uv run lint-imports -> Contracts: 10 kept, 0 broken
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-14 16:45
---
2026-10-14: plan approved by the human. Decisions confirmed: ownership lost returns False with a warning log (no exception); acquire_lease returns a bare str | None token (a Lease handle is left to TASK-58's lease facade); claim_token set only on NEW is held by docstring and conformance tests, no runtime guard. AC1 and AC2 sharpened and AC5 added.
---
<!-- COMMENTS:END -->
