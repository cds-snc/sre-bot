---
id: TASK-5
title: >-
  Rewrite idempotency store as atomic conditional claim behind an
  IdempotencyStore Protocol with in-memory fake
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-24 17:58'
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
Original single-PR framing under-scoped this rewrite's real blast radius. Decomposed on 2026-07-24 per the single-PR size gate (implementation-planning skill) into four subtasks, tracked here as the coordinator; this task's acceptance criteria are satisfied when all four are Done. Do not implement against this description directly - see the child tasks for the actual scoped plans.

Rationale (see decisions/reliability.md's new 'Idempotency is not a general job-status store' clause and Consequences bullet, and decisions/configuration.md's new 'Migration rides with whatever work already touches the domain' clause): the original scope conflated three distinct capabilities behind one get-then-put rewrite - true redelivery dedup, a concurrency lock/lease, and job-status polling - each needing its own migration, plus an orphaned legacy settings home that must move in the same change rather than wait for TASK-24.

Children (dependency order):
- TASK-5.1 - Idempotency: atomic claim/complete/release primitive, in-memory fake, and dedicated settings slice (foundational; no dependency on the others)
- TASK-5.2 - Idempotency: migrate Slack legacy_slack_listener dedup onto claim/complete/release (depends on TASK-5.1)
- TASK-5.3 - Idempotency: rewrite Access Sync platform/user concurrency lock onto claim/complete/release; align with TASK-6 (depends on TASK-5.1)
- TASK-5.4 - Access Sync: extract job-status polling into its own store; delete legacy IdempotencyService (depends on TASK-5.1; finishes the original 'delete the get-then-put path' once TASK-5.2/TASK-5.3 have moved their callers)

TASK-6 has been re-pointed to depend on TASK-5.1 and TASK-5.3 instead of this task directly (see TASK-6 for the coordination note on shared lease-helper reuse).
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decomposition rationale and slice sequence (per implementation-planning skill's single-PR size gate - trigger: mixes a mechanical rewrite with three unrelated behavior migrations, crosses subsystems app/infrastructure/idempotency, app/integrations/slack, and app/packages/access/sync, and cannot be reviewed or reverted as one PR):

1. TASK-5.1 (expand): new IdempotencyStore Protocol + ClaimResult, DynamoDB claim/complete/release rewrite, in-memory fake, dedicated settings.py, deletion of dead key_builder.py. Old IdempotencyService stack stays in place untouched - callers are not migrated yet.
2. TASK-5.2 (migrate - Slack dedup): app/integrations/slack/utils.py::legacy_slack_listener moves onto claim/complete/release; removes the prohibited payload-hash fallback key (flagged as an open product question, not resolved here).
3. TASK-5.3 (migrate - Access Sync lock): app/packages/access/sync/platform_lock.py moves onto the same primitive as a lease; coordinates with TASK-6 so its Tier-2 job lease reuses this lease helper instead of a second implementation.
4. TASK-5.4 (migrate + contract - job-status polling): extracts the job-runner/http/slack job-status reads and writes into their own small package-owned store (this was never idempotency), then deletes the legacy IdempotencyService/DynamoDBIdempotencyService/cache.py/service.py/factory.py once nothing references them - this is the final contract step that closes out the original 'delete the get-then-put path' DoD item.

Each child subtask carries its own AC-to-step traceability, test matrix, and blast-radius notes; see the child task files. This task stops at To Do - it tracks completion of the four children and is not itself implemented.
<!-- SECTION:PLAN:END -->
