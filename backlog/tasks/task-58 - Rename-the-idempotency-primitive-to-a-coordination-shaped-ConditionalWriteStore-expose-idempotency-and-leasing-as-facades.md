---
id: TASK-58
title: >-
  Rename the idempotency primitive to a coordination-shaped
  ConditionalWriteStore; expose idempotency and leasing as facades
status: To Do
assignee: []
created_date: '2026-07-28 13:19'
updated_date: '2026-09-24 20:09'
labels:
  - infrastructure
  - phase-4
  - reliability
  - plugin-architecture
milestone: m-7
dependencies:
  - TASK-6
  - TASK-102
  - TASK-106
references:
  - decisions/reliability.md
  - decisions/cloud-portability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1366'
  - decisions/plugin-architecture.md
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
- [ ] #1 The single atomic conditional-write primitive is exposed as one coordination-shaped Protocol (e.g. ConditionalWriteStore) with claim/complete/release in app/contracts/; the DynamoDB and in-memory implementations live in app/infrastructure/coordination/ and behave identically to today
- [ ] #2 IdempotencyStore and the lease helpers exist only as thin facades over that primitive; no second implementation of the conditional-write logic remains
- [ ] #3 All consumers import the new coordination paths; the old app/infrastructure/idempotency/ path and every transitional alias/shim are deleted (grep finds no idempotency-module import path)
- [ ] #4 The Access Sync job-status store remains a separate StorageService-backed keyed-record capability, not folded into the primitive
- [ ] #5 decisions/reliability.md lease.py path reference and any other decisions/ cross-references are updated to the new module path in the same PR
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All consumers migrated; tests green; no back-compat shim remains
- [ ] #2 PR references decisions/reliability.md and decisions/cloud-portability.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-17 20:40
---
2026-09-17, from planning TASK-25.2.5.4 (human decision to record it here).

The facade split this task builds is where the conditional-claim READ-FAILURE POLICY has to become an explicit per-use choice. Today one implicit default serves both uses, and the two uses want opposite defaults:

- LEASE facade: when the ConsistentRead after a contended claim fails, fail OPEN (return NEW). Per decisions/reliability.md a Tier-2 lease is a duplication optimization and the body is idempotent, so an unreadable read means only "cannot confirm exclusivity" - failing closed silently skips a whole scheduled period for no correctness gain. TASK-100 owns the flip; TASK-99 is its precondition (the bodies are not actually duplicate-safe yet, verified 2026-09-17).
- IDEMPOTENCY/DEDUP facade: fail CLOSED. The dedup record is the only evidence that an effect already happened, and the protected operation is explicitly NOT assumed idempotent - that is the whole point of the key. Under fail-open, a COMPLETED record plus a failed re-read means re-executing a completed operation and then overwriting its recorded outcome. TASK-37.2 is the first production dedup consumer; there is none today (get_idempotency_store has no production caller, verified 2026-09-17).

So the primitive should not carry a read-failure policy at all: each facade should choose, at construction or at the call, and the choice should be visible in the type rather than inherited. Reviewed against current lease and idempotent-consumer guidance on 2026-09-17, which makes the same point - one default cannot serve both.

Also for this task to carry forward: TASK-25.2.5.4 adds a fourth conditional-check-failure branch to claim() (an IN_PROGRESS record bearing the caller's own claim token resolves to NEW, defeating the SDK-replay hazard) and records it in decisions/reliability.md. It is an implementation-level defence against botocore's retry, deliberately NOT on the Protocol, so a Redis or Postgres adapter can answer the same hazard its own way. Keep it off the ConditionalWriteStore Protocol during the rename. TASK-102 is the separate, Protocol-level ownership question (release/complete gated on the token) and is the one that genuinely belongs with this task.
---

created: 2026-09-18 15:27
---
2026-09-18 (human decision): order is TASK-102, then this task, then TASK-100. This task is where the read-failure policy becomes explicit per use: the lease facade and the dedup facade each choose it at construction, and the primitive carries none. TASK-37.2 and TASK-100 now depend on this task. Not yet linked, needs coordinating: TASK-64 moves run_if_leased out of lease.py into the scheduler registry, and TASK-65 later deletes the _tier2 wrapper. Both touch the lease surface this task renames.
---

created: 2026-09-24 20:09
---
2026-09-24 alignment with decisions/plugin-architecture.md: the coordination contract is a core-service Protocol in app/contracts/, implemented in app/infrastructure/coordination/. AC#1 now names both homes, and this task depends on TASK-106 (contracts created). Consumers switch from the facades' module paths to registry resolution when the service registry lands (TASK-109, which depends on this task).
---
<!-- COMMENTS:END -->
