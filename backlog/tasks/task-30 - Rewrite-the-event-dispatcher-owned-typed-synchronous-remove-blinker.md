---
id: TASK-30
title: >-
  Retire the misused event dispatcher; defer the owned typed dispatcher until a
  real consumer (build-on-demand)
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-28 14:34'
labels:
  - infrastructure
  - phase-4
  - events
milestone: m-4
dependencies:
  - TASK-61
  - TASK-32
  - TASK-34
references:
  - decisions/events.md
  - claude-research-outcome.md
  - 'https://github.com/cds-snc/sre-bot/issues/1284'
priority: medium
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/events.md (revised 2026-07-28). Today app/infrastructure/events/service.py is string-keyed, blinker-backed with weak=False, and dispatches via ThreadPoolExecutor (breaking contextvars correlation inheritance). A 2026-07-28 architecture review concluded the app has NO genuine best-effort cross-feature reactor today: the sole cross-package hand-off (access/sync -> access/request via SYNC_COMPLETED/SYNC_FAILED) is durable workflow work that belongs on the approval workflow's queue step (approvals.md), and operator alerts ('no approvers found') call the notifications capability directly. Building a fresh dispatcher now would be speculative pub/sub with zero subscribers, contradicting the same build-on-demand discipline the durable queue follows (TASK-34).

Desired end state:
1. Remove blinker from dependencies and uv.lock; delete the ThreadPoolExecutor dispatch path and the string-keyed event service.
2. SYNC_COMPLETED/SYNC_FAILED no longer flow through the event bus (moved to the approval workflow's queue-borne step by the access/request refactor + QueueService tasks).
3. The operator-alert path no longer publishes an event (rehomed onto the notifications capability, TASK-32).
4. Do NOT build a replacement dispatcher. The owned, typed, synchronous dispatcher design in events.md (frozen-dataclass events, class-keyed publish, inline in-order delivery, per-subscriber isolation, publish-after-commit, hookspec subscription) is preserved as the design to instantiate on demand, and lands with its first genuine consumer.

This is a cleanup task that closes after its consumers are rehomed by their own tasks. The task-planner agent should sequence it after those moves.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dispatcher tests: registration order, error isolation, contextvar (request_id) inheritance into subscribers, async subscriber support
- [ ] #2 grep: no blinker imports anywhere; blinker removed from dependencies and uv.lock
- [ ] #3 No string event names at publish sites - publishing is keyed by event class
- [ ] #4 grep: no blinker imports anywhere; blinker removed from dependencies and uv.lock
- [ ] #5 The ThreadPoolExecutor dispatch path and the string-keyed event service are deleted
- [ ] #6 SYNC_COMPLETED/SYNC_FAILED no longer flow through the event bus (moved to the approval workflow queue step)
- [ ] #7 The operator-alert path no longer publishes an event (routed to the notifications capability)
- [ ] #8 No new speculative dispatcher is introduced; events.md documents the deferred build-on-demand design
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All existing event flows migrated; tests green
- [ ] #2 PR references decisions/events.md
- [ ] #3 No dead event-bus code remains; dependent moves (queue step, notifications) are tracked by their own tasks
- [ ] #4 PR references decisions/events.md
<!-- DOD:END -->
