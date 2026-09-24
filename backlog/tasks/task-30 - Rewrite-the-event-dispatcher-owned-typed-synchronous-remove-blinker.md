---
id: TASK-30
title: >-
  Delete the in-process event dispatcher, blinker and the
  register_event_handlers hookspec; build no replacement
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-24 20:04'
labels:
  - infrastructure
  - phase-4
  - events
milestone: m-4
dependencies:
  - TASK-61
  - TASK-34
references:
  - claude-research-outcome.md
  - 'https://github.com/cds-snc/sre-bot/issues/1284'
  - decisions/plugin-architecture.md
  - decisions/plugins.md
  - decisions/hookspec-deprecation.md
priority: medium
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-09-24. decisions/events.md was deleted. decisions/plugin-architecture.md: "There is no in-process event bus." The app runs as two or more replicas, so an in-process event reaches only the replica that raised it. A plugin reacts to something another plugin does through an extension point owned by the capability where it happens (collected once at startup), or through the queue contract when the reaction must reach every replica or survive a restart. plugins.md: the in-process event dispatcher and the register_event_handlers hookspec are not a supported mechanism.

Today app/infrastructure/events/ is string-keyed and blinker-backed (weak=False), dispatches through a ThreadPoolExecutor (breaking contextvars correlation), and is used only by access/request and access/sync:
- access/sync subscribes to REQUEST_APPROVED;
- access/request subscribes to SYNC_COMPLETED and SYNC_FAILED, each through register_handler inside startup_warmup;
- access/request raises the "no approvers found" operator alert as an event.
register_event_handlers has no implementations.

End state: the dispatcher, blinker and the hookspec are deleted, and nothing replaces them. The earlier plan to keep an "owned typed dispatcher" design for on-demand use is dropped: that design lived in the deleted record, and plugin-architecture.md rules the mechanism out.

Sequencing: this is a cleanup that closes after its consumers are rehomed.
- TASK-61 moves the request <-> sync continuation to the approvals engine: approval triggers the access effect handler, and the sync result returns over the queue contract (TASK-34).
- TASK-61 sends the operator alert through the notifications capability.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 grep: no blinker import anywhere; blinker removed from dependencies and uv.lock
- [ ] #2 app/infrastructure/events/ (string-keyed service, ThreadPoolExecutor dispatch path) is deleted with no replacement dispatcher
- [ ] #3 The register_event_handlers hookspec is deleted following decisions/hookspec-deprecation.md's removal checklist (zero implementers, boot-test inventory updated)
- [ ] #4 grep: no dispatch_background, get_event_dispatcher or register_handler call remains in app/
- [ ] #5 decisions/plugins.md, feature-packages.md, lifecycle.md and approvals.md drop their event-dispatcher tolerances in the same PR
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All existing event flows migrated; tests green
- [ ] #2 PR references decisions/events.md
- [ ] #3 No dead event-bus code remains; dependent moves (queue step, notifications) are tracked by their own tasks
- [ ] #4 PR references decisions/events.md
<!-- DOD:END -->
