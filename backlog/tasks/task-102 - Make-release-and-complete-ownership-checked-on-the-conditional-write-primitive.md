---
id: TASK-102
title: Make release and complete ownership-checked on the conditional-write primitive
status: To Do
assignee: []
created_date: '2026-09-17 20:40'
updated_date: '2026-09-17 20:47'
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
- [ ] #1 A claimant whose claim was taken over after its in-progress TTL elapsed cannot delete or overwrite the new holder's record
- [ ] #2 The ownership token travels from claim to release/complete through the Protocol rather than through implementation-local state
- [ ] #3 The in-memory implementation enforces the same ownership rule, so the conformance suite covers both
- [ ] #4 The limits are written down: this prevents a stale holder destroying a live claim; it does not make lease-protected execution exactly-once
<!-- AC:END -->
