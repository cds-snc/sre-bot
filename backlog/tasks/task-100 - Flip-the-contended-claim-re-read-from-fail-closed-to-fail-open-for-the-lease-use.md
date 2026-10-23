---
id: TASK-100
title: >-
  Flip the contended-claim re-read from fail-closed to fail-open for the lease
  use
status: To Do
assignee: []
created_date: 2026-09-17 20:39
updated_date: '2026-10-23T17:08:00Z'
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
  - TASK-58.2
references:
  - decisions/reliability.md
  - app/infrastructure/coordination/dynamodb.py
  - app/infrastructure/coordination/lease.py
  - https://github.com/cds-snc/sre-bot/issues/1650
priority: high
ordinal: 228000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Depends on TASK-99: the flip is correct only once the job bodies it exposes are safe to run twice.

CURRENT CODE. ConditionalWriteStore.claim() (infrastructure/coordination/dynamodb.py:100-124) returns INDETERMINATE when the ConsistentRead after a contended conditional put fails with a classified error; an unclassified error re-raises. Each facade resolves INDETERMINATE through its ReadFailurePolicy (contracts/coordination/policy.py), which has only FAIL_CLOSED, and build_lease_store sets FAIL_CLOSED for every lease (infrastructure/coordination/factory.py:25-29). run_if_leased (infrastructure/coordination/lease.py) therefore skips the run, and a singleton job silently does not run for a whole period.

WHY FLIP. decisions/reliability.md holds that a Tier-2 lease is a duplication optimization and never a correctness mechanism, and that duplicate execution is acceptable because bodies are idempotent. Under that doctrine an unreadable re-read means only 'cannot confirm exclusivity', so failing closed buys no correctness and costs availability. Current lease and idempotent-consumer guidance agrees for a lease whose body is idempotent, and is explicit that a lock holder must be prepared for its lock to be taken away.

SCOPE
- Add a fail-open member to ReadFailurePolicy; the lease facade resolves INDETERMINATE to 'proceed' under it, and the policy docstring records why.
- The fail-open lease holds no record it wrote: its release must free nothing. The ownership-checked release (TASK-102) refuses a token that matches no record; how acquire reports a fail-open lease (a token that matches no record, or a marker the caller's release skips) is decided at planning.
- The IdempotencyStore (dedup) keeps FAIL_CLOSED: fail-open there would re-execute a completed operation and let complete() overwrite its outcome (TASK-37.2 adds the first dedup consumer).
- packages/access/sync/providers.py also builds its lease through build_lease_store; planning decides whether it flips with the scheduled jobs (its body must then be safe to run twice) or keeps FAIL_CLOSED explicitly.
- Tests that pin the lease's fail-closed resolution (tests/unit/contracts/coordination/test_coordination_policy.py, test_coordination_lease_store.py, tests/unit/infrastructure/coordination/test_coordination_store_factory.py, test_coordination_run_if_leased.py) are inverted, not deleted.
- The unclassified-error path is not part of this flip: an unknown fault is not evidence of anything, so it stays a raise.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Under the lease facade, a classified failure of the contended re-read lets the caller run (fail-open); ReadFailurePolicy's docstring records why fail-open fits a lease whose body is idempotent
- [ ] #2 A fail-open lease cannot delete or overwrite another holder's record: its release frees nothing (tested against the ownership-checked release)
- [ ] #3 The IdempotencyStore keeps FAIL_CLOSED; each facade's policy stays an explicit choice at construction, and the access sync lease's policy is stated explicitly
- [ ] #4 An unclassified error on the re-read still propagates unchanged
- [ ] #5 The tests pinning the lease's fail-closed resolution are updated in this PR rather than left contradicting the new behaviour
- [ ] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
