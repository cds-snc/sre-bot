---
id: TASK-58
title: >-
  Rename the idempotency primitive to a coordination-shaped
  ConditionalWriteStore; expose idempotency and leasing as facades
status: To Do
assignee: []
created_date: '2026-07-28 13:19'
updated_date: '2026-07-28 13:32'
labels:
  - infrastructure
  - phase-4
  - reliability
milestone: m-4
dependencies:
  - TASK-6
references:
  - decisions/reliability.md
  - decisions/cloud-portability.md
priority: medium
ordinal: 88000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/reliability.md and decisions/cloud-portability.md (architecture review, 2026-07-28). The service at app/infrastructure/idempotency/ is named after ONE of its uses. What it actually provides is the single atomic conditional-write (compare-and-set) coordination primitive that reliability.md already says backs three distinct capabilities: idempotency dedup, Tier-2 leases, and outbox claims ("instances of the one conditional-write contract"). The narrow "idempotency" name is what invites the recurring "could SQS/DynamoDB Streams replace this?" confusion (neither can - only a conditional write gives mutual exclusion). DynamoDB stays as the backing service; this is a naming/shape correction, not a backend swap.

End state (full prune, no back-compat shim - per the refactor mandate):
1. Rename app/infrastructure/idempotency/ to a coordination-shaped home (e.g. app/infrastructure/coordination/) exposing the primitive Protocol ConditionalWriteStore (or AtomicClaimStore) with the existing claim/complete/release surface and DynamoDB + in-memory implementations unchanged in behavior.
2. Keep IdempotencyStore (dedup) and the lease helpers (acquire_lease/release_lease, lease.py, plus TASK-6's TTL-parameterized lease-store factory and acquire+run+release wrapper if landed) as thin, capability-shaped FACADES over the primitive - preserving reliability.md's rule that each USE gets its own capability-shaped Protocol while there is exactly one implementation of the primitive.
3. Migrate ALL consumers (idempotency dedup callers, Access Sync lease, scheduler Tier-2 leases) to the new import paths. Delete the old app/infrastructure/idempotency/ module path and any transitional import alias/shim outright - no backward-compatible re-export left behind.
4. Preserve the reliability.md guard: a job-STATUS poll store (Access Sync JobStatusStore) is NOT this primitive and stays a separate StorageService-backed keyed-record capability; do not fold it in during the rename.
5. Update decisions/reliability.md's lease.py path reference and any other decisions/ cross-references to the new module path in the same PR (governance.md cascade rule).

Ordering: coordinate with TASK-6 (the scheduler Tier-2 lease consumer, which adds helpers to lease.py). Land this AFTER TASK-6 so the rename migrates TASK-6's call sites too rather than racing them; if TASK-6 slips, this task still migrates whatever consumers exist at the time with no shim.

This is a rename + facade split with no wire-behavior change; a planner agent should confirm it fits one reviewable PR or decompose it (e.g. primitive-rename slice, then facade + consumer-migration slice, then old-path deletion) per the single-PR size gate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The single atomic conditional-write primitive is exposed as one coordination-shaped Protocol (e.g. ConditionalWriteStore) with claim/complete/release; DynamoDB and in-memory implementations behave identically to today
- [ ] #2 IdempotencyStore and the lease helpers exist only as thin facades over that primitive; no second implementation of the conditional-write logic remains
- [ ] #3 All consumers import the new coordination module; the old app/infrastructure/idempotency/ path and every transitional alias/shim are deleted (grep finds no idempotency-module import path)
- [ ] #4 The Access Sync job-status store remains a separate StorageService-backed keyed-record capability, not folded into the primitive
- [ ] #5 decisions/reliability.md lease.py path reference and any other decisions/ cross-references are updated to the new module path in the same PR
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All consumers migrated; tests green; no back-compat shim remains
- [ ] #2 PR references decisions/reliability.md and decisions/cloud-portability.md
<!-- DOD:END -->
