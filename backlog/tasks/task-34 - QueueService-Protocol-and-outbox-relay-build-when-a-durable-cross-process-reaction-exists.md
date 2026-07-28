---
id: TASK-34
title: >-
  QueueService Protocol and outbox relay (build when a durable cross-process
  reaction exists)
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-28 14:34'
labels:
  - infrastructure
  - phase-4
  - reliability
milestone: m-4
dependencies:
  - TASK-5
references:
  - decisions/reliability.md
  - claude-research-outcome.md
  - 'https://github.com/cds-snc/sre-bot/issues/1288'
priority: low
ordinal: 34000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/reliability.md (Queuing, Outbox) and claude-research-outcome.md: cross the cloud boundary only when a reaction must outlive a crash. Do NOT build speculatively - start this task when the first real consumer appears (e.g. the incident or webhooks migration needs durable work).

Steps when triggered:
1. QueueService Protocol (capability-shaped: send/receive/ack semantics, at-least-once, possibly out of order) + SQS implementation + in-memory fake.
2. Messages are control-plane signals: small, carrying correlation_id and intent; consumers re-fetch state from the store and authorize against the fetched entity; consumers idempotent via task-5 primitive.
3. Outbox table written in the same transaction as the state change; async relay; DLQ after bounded receives with alarm; DLQ replay is an authenticated operator action.
4. No "exactly-once" claims anywhere - at-least-once plus idempotent consumers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 QueueService Protocol has an in-memory fake exercised by the integration suite
- [ ] #2 Consumer template demonstrates: idempotency claim, state re-fetch, visibility-timeout extension honoring retry_after
- [ ] #3 DLQ alarm exists; replay requires an authenticated principal
- [ ] #4 grep: no exactly-once claims in code or docs
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 First real consumer migrated onto it as part of the same series
- [ ] #2 PR references decisions/reliability.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 13:20
---
Scope refinement from a 2026-07-28 architecture review: (1) Relay choice - prefer a POLLING relay (polling-publisher pattern) as the portable default for the outbox; treat DynamoDB Streams (transaction-log-tailing) as an AWS-only latency optimization behind the SAME relay Protocol, never leaking Streams into feature code. reliability.md updated to state this. (2) These three primitives are NOT interchangeable: the conditional-write store (TASK-58 / idempotency-coordination) gives mutual exclusion + dedup; QueueService gives durable at-least-once work; DynamoDB Streams only relays committed writes. QueueService sits BESIDE the conditional-write store, never replaces it. (3) Concrete triggers that make this non-speculative now: the notifications rebuild (TASK-32 - durable 'must deliver even if we crash' delivery is QueueService work, not a bespoke queue) and the retry-store consolidation (TASK-59, which depends on this task and folds app/infrastructure/resilience/retry/ onto QueueService). (4) Full-end-state mandate: ship the QueueService capability + SQS adapter + in-memory fake + DLQ/redrive as the single durable-queue owner; no bespoke per-feature durable queues survive alongside it.
---

created: 2026-07-28 14:34
---
2026-07-28 approvals architecture (decisions/approvals.md): the generic approval-workflow capability adds a third concrete, non-speculative consumer for this task. Its cross-package effect steps and the reclassified access/sync -> access/request advance (SYNC_COMPLETED/SYNC_FAILED, moved off the event bus per events.md) are durable workflow steps that ride the outbox/QueueService. TASK-61 (access/request refactor) depends on this; TASK-60 (approvals capability) designs its steps to hand off over this queue. Alongside notifications (TASK-32) and retry consolidation (TASK-59), the durable-work triggers now clearly exist.
---
<!-- COMMENTS:END -->
