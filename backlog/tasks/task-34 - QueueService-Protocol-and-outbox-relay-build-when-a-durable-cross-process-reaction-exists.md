---
id: TASK-34
title: >-
  QueueService Protocol and outbox relay (build when a durable cross-process
  reaction exists)
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:58'
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
