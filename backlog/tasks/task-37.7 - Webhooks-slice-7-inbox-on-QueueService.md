---
id: TASK-37.7
title: 'Webhooks slice 7: inbox on QueueService'
status: To Do
assignee: []
created_date: '2026-11-25T20:49:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.5
  - TASK-34
  - TASK-113
references:
  - decisions/webhooks.md
  - decisions/reliability.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-37
priority: medium
ordinal: 549000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Version 2 of the inbox (TASK-168 research packet section 5, row 37.7, and Q5 step 8; decisions/reliability.md Queuing). Off the TASK-40 path. Carries the surviving intent of the old TASK-37.5 (multi-sink dispatch: the durable-enqueue target through the queue contract, never a bespoke queue) and its TASK-34 and TASK-113 dependencies.

Scope: once TASK-34 builds QueueService, the inline processor becomes an enqueue of the inbox item and the sweeper becomes the queue consumer plus a dead-letter queue that alerts. The inbox item remains the delivery log and the dedupe is unchanged. Consumers and handlers are still the ones registered through the webhooks hookspec, collected once at startup by the extension-point phase (TASK-113). The webhook inbox may itself be the durable cross-process reaction that justifies building TASK-34 (OQ19).

Out of scope: any change to protocols, content or the management plane.

Size: ~150 production LOC.
Production: prod (internal processing path).
Revert / blast radius: one revert restores inline processing plus the sweeper.
Change notice: none expected (no caller-visible change); confirm at planning.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The inline processor enqueues the inbox item through the QueueService contract and a consumer processes it; items past the retry cap go to the dead-letter queue and alert (test)
- [ ] #2 The inbox item remains the delivery log and delivery-id dedupe is unchanged (test)
- [ ] #3 No bespoke queue and no in-process event dispatcher is introduced (grep: no dispatch_background, register_handler or blinker in the capability)
- [ ] #4 Consumers and handlers are collected once at startup through the extension-point phase; no pluggy hook is called per request (test)
- [ ] #5 TASK-36 smoke tests pass; existing Slack-render webhooks are unaffected
<!-- AC:END -->
