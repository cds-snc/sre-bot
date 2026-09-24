---
id: TASK-37.5
title: >-
  Webhooks slice 5: multi-sink dispatch fan-out (registered-handler and
  durable-enqueue targets)
status: To Do
assignee: []
created_date: '2026-07-28 18:40'
updated_date: '2026-09-24 20:04'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.4
  - TASK-34
  - TASK-113
references:
  - decisions/webhooks.md
  - decisions/reliability.md
  - decisions/feature-packages.md
  - 'https://github.com/cds-snc/sre-bot/issues/1380'
  - decisions/plugin-architecture.md
  - decisions/plugins.md
parent_task_id: TASK-37
priority: medium
ordinal: 100000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 of the webhooks rearchitecture (decisions/webhooks.md; coordinator TASK-37). Rescoped 2026-09-24. The deleted decisions/events.md no longer applies. There is no in-process event bus (decisions/plugin-architecture.md), so the former "domain event" target becomes a handler that a feature registers through the webhooks capability's extension point.

Adds dispatch targets beyond the transport render, so an inbound webhook can trigger another business feature without the capability importing it.

Scope:
1. dispatch.py: generalize the single Slack render target (TASK-37.3) into a Target abstraction with exactly one kind per target: TRANSPORT_RENDER, REGISTERED_HANDLER or DURABLE_ENQUEUE. The Webhook record declares one or more targets, and dispatch fans the intent out to each.
2. Registered-handler target: app/capabilities/webhooks/hookspecs.py declares the extension point. Features return typed alert-action or source handlers from it, collected once at startup by the host's extension-point phase (TASK-113). At dispatch the capability awaits the handler's async method. The incident feature's alert actions (today the hook_type == "alert" incident button) are the known first consumer. Wire the target live only for a consumer that exists at implementation time; otherwise land the type behind a validation guard.
3. Durable-enqueue target: enqueue a small control-plane message through the queue contract (TASK-34). Until TASK-34 is Done, the target type fails validation with a clear message. No bespoke queue.
4. Configuration: targets are part of the Webhook record and WebhookSettings. Document the shape and how an operator configures a webhook to fan out.
Out of scope: HMAC and lifecycle (TASK-47), the enforcement burn-down (TASK-48).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dispatch supports multiple declared targets per webhook, each of exactly one kind: transport render, registered handler or durable enqueue (test)
- [ ] #2 A feature registers a handler through the webhooks hookspecs extension point, collected once at startup; the capability never imports the feature, and no pluggy hook is called per request (test)
- [ ] #3 The durable-enqueue target uses the queue contract, or fails validation clearly until TASK-34 lands; no bespoke queue is introduced (test)
- [ ] #4 No in-process event dispatcher is used or introduced (grep: no dispatch_background, register_handler or blinker in the capability)
- [ ] #5 TASK-36 smoke tests pass; existing Slack-render webhooks are unaffected
<!-- AC:END -->
