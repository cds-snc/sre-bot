---
id: TASK-59
title: >-
  Consolidate the DynamoDB RetryStore onto QueueService; delete the
  unimplemented SQS retry backend
status: To Do
assignee: []
created_date: '2026-07-28 13:20'
updated_date: '2026-09-15 20:06'
labels:
  - infrastructure
  - phase-4
  - reliability
milestone: m-4
dependencies:
  - TASK-34
references:
  - decisions/reliability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1367'
priority: medium
ordinal: 89000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/reliability.md (Queuing, Outbound retry; architecture review 2026-07-28). app/infrastructure/resilience/retry/ is, functionally, a hand-rolled durable retry queue on DynamoDB (RetryStore Protocol with save/fetch_due/claim_record/mark_success/mark_permanent_failure, a GSI-backed due-scan, a DLQ dict, and exponential backoff). Its RetrySettings.backend enum already advertises an "sqs" value that is NOT implemented - a phantom option. Once TASK-34 delivers the QueueService capability (SQS + DLQ + redrive + in-memory fake), most of what RetryStore does is native queue behavior; keeping a bespoke DynamoDB reimplementation beside it duplicates the durable-work primitive reliability.md says should have exactly one owner.

End state (full prune, no back-compat shim - per the refactor mandate):
1. Delete the unimplemented "sqs" value from the RetrySettings backend enum now (it is dead configuration surface regardless of the rest of this task). Do NOT implement an SQS RetryStore backend - build/route through QueueService instead.
2. After TASK-34 lands, decide deliberately and record the decision: fold the retry/redelivery mechanism onto QueueService (at-least-once + DLQ + visibility-timeout backoff) for every consumer whose need SQS-native semantics cover, migrating each RetryProcessor consumer.
3. Retain a DynamoDB-backed store ONLY for the narrow residue SQS genuinely cannot express - delayed/scheduled retries beyond SQS's 15-minute max DelaySeconds, or app-controlled backoff curves - and scope it down to exactly that. If no such residue survives triage, delete app/infrastructure/resilience/retry/ entirely (store, dynamodb_store, in-memory, factory, worker) rather than leaving a redundant second durable-queue implementation.
4. Migrate all consumers; delete the old retry-store paths and any transitional shims outright; no backward-compatible re-export.
5. Keep the circuit breaker (app/infrastructure/resilience/circuit_breaker.py) as-is - it is a separate, per-replica in-process concern (see decisions/reliability.md), not part of this consolidation.

Depends on TASK-34 (QueueService must exist before retry can fold onto it). Step 1 (delete the phantom sqs enum value) can land independently/first. A planner agent should confirm the consolidation fits one reviewable PR or decompose it (phantom-enum deletion, then per-consumer migration, then retry-store deletion/scope-down) per the single-PR size gate, and must surface the "delete entirely vs retain scheduled-retry residue" decision to the human before deletion.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The unimplemented sqs value is removed from the RetrySettings backend enum; no phantom backend option remains
- [ ] #2 The retry/redelivery mechanism routes through QueueService (at-least-once + DLQ) for every consumer SQS-native semantics cover; no bespoke second durable-queue implementation runs beside QueueService
- [ ] #3 Any retained DynamoDB store is scoped strictly to the SQS-inexpressible residue (scheduled/delayed retries beyond 15-min DelaySeconds); if none survives triage, app/infrastructure/resilience/retry/ is deleted entirely
- [ ] #4 All RetryProcessor consumers migrated; old retry-store paths and transitional shims deleted; the circuit breaker is left untouched
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Retry consumers migrated onto QueueService; tests green; no back-compat shim remains
- [ ] #2 PR references decisions/reliability.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-15 20:06
---
2026-09-15 follow-up from TASK-25.2.5 planning (human decision): three classify-and-continue sites in infrastructure/resilience/retry/dynamodb_store.py were found and deliberately NOT fixed in TASK-25.2.5, because the DynamoDB retry store is not used in production today (RetrySettings.backend defaults to "memory", and create_retry_store / get_resilience_service / RetryWorker are only constructed in tests). Decide raise vs keep for each one when this task consolidates or deletes the store:
- fetch_due (~:162-169): a query failure logs dynamodb_fetch_due_failed and returns [], so a DynamoDB outage looks like "nothing due".
- increment_attempt (~:334-347): a get_item failure logs retry_record_not_found_for_increment and returns without incrementing, so the record is retried again at its old schedule.
- _count_by_status (~:424-445): a query failure returns None, which get_stats reports as a count.
If the store is deleted outright (AC#3), these go with it and no decision is needed.
---
<!-- COMMENTS:END -->
