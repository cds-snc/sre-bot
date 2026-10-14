---
id: TASK-58.2
title: >-
  Lease and idempotency facades over ConditionalWriteStore with an explicit
  per-facade read-failure policy
status: To Do
assignee: []
created_date: '2026-10-14 17:45'
updated_date: '2026-10-14 17:54'
labels:
  - infrastructure
  - reliability
  - plugin-architecture
milestone: m-7
dependencies:
  - TASK-58.1
parent_task_id: TASK-58
priority: medium
ordinal: 381000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-58 (Stack C layer 3). Builds the per-use facades over the primitive that TASK-58.1 moved; behaviour stays as today.

Decided 2026-10-14 (human):
- The primitive carries no read-failure policy. When the consistent re-read after a contended claim fails, DynamoDB claim() returns a new ClaimResult.INDETERMINATE with no claim token, and each facade maps it. Both facades map it to IN_PROGRESS here (fail-closed), so behaviour is unchanged. This keeps "claim_token is set exactly on NEW" intact; TASK-100 later flips only the lease facade and skips the release when no token is held.
- Each facade takes a required read-failure policy at construction, with no default. The policy enum has only FAIL_CLOSED; TASK-100 adds FAIL_OPEN.
- The facades are pure logic over the Protocol and live in app/contracts/coordination/, importing only the standard library and contracts.
- The idempotency (dedup) facade is built here although it has no production caller until TASK-37.2.
- run_if_leased stays a plain function so TASK-64 can move it mechanically. get_lease_store(ttl) becomes a provider in infrastructure/coordination/factory.py.
- Access Sync's platform_lock and providers, and jobs/scheduled_tasks, use the lease facade; the platform_lock import-linter ignore entry is removed.
- get_idempotency_store and reset_idempotency_store (no production caller) are deleted.
- Facade class names: LeaseStore (lease facade: acquire, release; run_if_leased stays a function) and IdempotencyStore (idempotency facade: claim, complete, release). Lease and idempotency are the industry terms (Kubernetes Lease, Dapr and Redis lock leases; Camel IdempotentRepository, Powertools idempotency) and Store matches RecordStore and JobStatusStore. IdempotencyStore returns with a new meaning one layer after TASK-58.1 renames the primitive away from it; the PR description says so.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 LeaseStore (lease) and IdempotencyStore (idempotency) facades in app/contracts/coordination/ wrap ConditionalWriteStore; each is constructed with a required read-failure policy, and both are fail-closed
- [ ] #2 The primitive carries no read-failure policy: a failed contended re-read is reported as ClaimResult.INDETERMINATE with no claim token, and the facades map it to IN_PROGRESS
- [ ] #3 No second implementation of the conditional-write logic remains, and the DynamoDB own-replay branch is not on the Protocol
- [ ] #4 Access Sync and the scheduler use LeaseStore; the platform_lock import-linter ignore entry is removed; get_conditional_write_store and reset_conditional_write_store are deleted
- [ ] #5 decisions/reliability.md describes the facades and the per-facade policy, with a dated change entry
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-14 17:54
---
2026-10-14 (human): facade names are LeaseStore and IdempotencyStore (chosen over LeaseProvider/IdempotentRepository, which clash with this codebase's providers.py and have no repository precedent here).
---
<!-- COMMENTS:END -->
