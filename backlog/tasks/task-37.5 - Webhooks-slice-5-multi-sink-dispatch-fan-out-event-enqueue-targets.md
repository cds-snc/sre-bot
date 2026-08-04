---
id: TASK-37.5
title: 'Webhooks slice 5: multi-sink dispatch fan-out (event/enqueue targets)'
status: To Do
assignee: []
created_date: '2026-07-28 18:40'
updated_date: '2026-07-28 19:16'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.4
  - TASK-34
references:
  - decisions/webhooks.md
  - decisions/events.md
  - decisions/reliability.md
  - decisions/feature-packages.md
  - 'https://github.com/cds-snc/sre-bot/issues/1380'
parent_task_id: TASK-37
priority: medium
ordinal: 100000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 of the webhooks rearchitecture (decisions/webhooks.md; coordinator TASK-37). Adds dispatch targets beyond Slack - domain events and durable enqueue - so an inbound webhook can trigger OTHER business features without feature-to-feature imports (decisions/feature-packages.md, events.md, reliability.md). Build-on-demand: do NOT build speculative pub/sub.

Scope:
1. dispatch.py: generalize the single Slack render target (TASK-37.3) into a Target abstraction with exactly one kind per target - TRANSPORT_RENDER, DOMAIN_EVENT, DURABLE_ENQUEUE. The Webhook record declares one or more targets; dispatch fans the intent to each.
2. Domain-event target: publish a past-tense fact via the infrastructure events dispatcher (decisions/events.md). Per events.md build-on-demand, only wire this live if a REAL subscriber exists at implementation time; otherwise land the target TYPE + validation and defer live wiring with a comment. Never introduce a dispatcher with zero subscribers.
3. Durable-enqueue target: enqueue a small control-plane message via QueueService (decisions/reliability.md); gated on TASK-34 (QueueService + outbox relay). If TASK-34 is not yet Done, land the target type behind a clear NotImplemented/validation guard (a webhook configured for enqueue fails validation with a clear message) and add the real path when TASK-34 lands. No bespoke queue.
4. Configuration: targets are part of the Webhook record / WebhookSettings; document the shape and how an operator configures a webhook to fan out.

Out of scope: HMAC/lifecycle (TASK-47), enforcement burn-down (TASK-48).

Verify: whether any real cross-feature consumer exists yet. If none, this slice is mostly the Target abstraction + the existing Slack target, with event/enqueue behind clear guards - flag for human decision rather than building speculative machinery.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dispatch supports multiple declared targets per webhook, each of exactly one kind: transport render, domain event, or durable enqueue (test)
- [ ] #2 A webhook can be configured to publish a domain event another feature subscribes to, with no import of that feature from the webhooks package; live wiring only if a real subscriber exists, otherwise the target type plus a guard (test)
- [ ] #3 The durable-enqueue target uses QueueService, or fails validation clearly until TASK-34 lands; no bespoke queue is introduced (test)
- [ ] #4 No speculative event dispatcher with zero subscribers is introduced (review against events.md build-on-demand)
- [ ] #5 TASK-36 smoke tests pass; existing Slack-render webhooks are unaffected
<!-- AC:END -->
