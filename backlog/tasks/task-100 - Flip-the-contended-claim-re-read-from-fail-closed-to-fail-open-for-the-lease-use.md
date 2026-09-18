---
id: TASK-100
title: >-
  Flip the contended-claim re-read from fail-closed to fail-open for the lease
  use
status: To Do
assignee: []
created_date: '2026-09-17 20:39'
updated_date: '2026-09-18 15:27'
labels:
  - infrastructure
  - reliability
  - phase-4
milestone: m-4
dependencies:
  - TASK-25.2.5.4
  - TASK-99
  - TASK-102
  - TASK-58
references:
  - decisions/reliability.md
  - app/infrastructure/idempotency/dynamodb.py
  - app/infrastructure/idempotency/lease.py
priority: high
ordinal: 228000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human decision 2026-09-17, taken while planning TASK-25.2.5.4, backed by a web-research review the same day. Depends on TASK-99: the flip is correct only once the job bodies it exposes are safe to run twice.

TODAY. claim() in app/infrastructure/idempotency/dynamodb.py (lines 88-95 before TASK-25.2.5.4) returns IN_PROGRESS when the ConsistentRead after a contended conditional put fails with a CLASSIFIED error. The caller therefore skips the run. TASK-25.2.5.4 keeps that behaviour and records in the claim() docstring that it is provisional and lease-scoped.

WHY FLIP. decisions/reliability.md holds that a Tier-2 lease is a duplication optimization and never a correctness mechanism, and that duplicate execution is acceptable because bodies are idempotent. Under that doctrine an unreadable re-read means only "cannot confirm exclusivity", not "risk an unsafe duplicate effect", so failing closed buys no correctness and costs availability: the singleton job silently does not run for a whole period. Current lease and idempotent-consumer guidance (reviewed 2026-09-17) agrees for a lease whose body is idempotent, and is explicit that a lock holder must be prepared for its lock to be taken away.

WHY IT IS NOT A ONE-LINE CHANGE. Three things have to be handled together:
1. We reach the re-read only because our conditional put definitively FAILED, so someone else's record exists. Returning NEW tells the caller it holds a lease it provably does not hold. run_if_leased (app/infrastructure/idempotency/lease.py:33-41) then releases in a finally via an unconditional delete_item, deleting the real holder's claim and potentially cascading to a third holder. Either land the ownership-checked release task created alongside this one first, or make the fail-open path skip the release.
2. Fail-open is correct for a LEASE and wrong for DEDUP. If the existing record is COMPLETED and the re-read fails, fail-open re-executes a completed operation and complete() then overwrites the recorded outcome. There is no dedup consumer in production today (get_idempotency_store has no production caller, verified 2026-09-17) but TASK-37.2 adds one. The policy must therefore be an explicit per-use choice, not one implicit default - see the comment left on TASK-58, which builds the idempotency and lease facades over the one primitive and is where that choice naturally lives.
3. TASK-25.2.5.4's AC#1 and its unit test pin the current fail-closed behaviour. Both are reworded and inverted here, not deleted quietly.

The unclassified-error path is NOT part of this flip: classify_aws_error re-raises an unknown error code, and an unknown fault is not evidence of anything. It stays a raise.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A classified failure of the ConsistentRead after a contended claim returns NEW for the lease use, and the claim() docstring records why, superseding the fail-closed rationale written by TASK-25.2.5.4
- [ ] #2 The fail-open path cannot delete or overwrite another holder's record: either release is ownership-checked, or the fail-open claim is marked so the caller's release is skipped
- [ ] #3 The dedup use keeps fail-closed, and the two policies are an explicit choice at the call site or facade rather than one shared default
- [ ] #4 An unclassified error on the re-read still propagates unchanged
- [ ] #5 TASK-25.2.5.4's AC#1 and its unit test are updated in this PR rather than left contradicting the new behaviour
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-18 15:27
---
2026-09-18 (human decision): order is TASK-102, then TASK-58, then TASK-100. TASK-58 creates the per-use read-failure policy in the lease and dedup facades, set at construction. This task then only flips the lease facade to fail-open. AC#3 is satisfied by TASK-58's facade split rather than by a new parameter on today's IdempotencyStore. TASK-101 folds into this task's policy decision afterwards.
---
<!-- COMMENTS:END -->
