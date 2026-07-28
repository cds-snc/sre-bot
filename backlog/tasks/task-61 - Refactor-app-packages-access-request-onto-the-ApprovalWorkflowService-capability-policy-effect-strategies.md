---
id: TASK-61
title: >-
  Refactor app/packages/access/request onto the ApprovalWorkflowService
  capability (policy + effect strategies)
status: To Do
assignee: []
created_date: '2026-07-28 14:33'
labels:
  - access
  - approvals
  - phase-4
milestone: m-4
dependencies:
  - TASK-60
  - TASK-34
  - TASK-32
references:
  - decisions/approvals.md
  - decisions/events.md
priority: high
ordinal: 91000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/approvals.md and decisions/events.md. Refactor app/packages/access/request to consume the generic ApprovalWorkflowService (TASK for infrastructure/approvals extraction) by supplying access-specific ApprovalPolicy and EffectHandler strategies, and retire the two mis-routed mechanisms it currently relies on.

Desired end state:
1. access/request holds only access-specific policy + effect strategies (approver resolution, thresholds, the grant/revoke effect); all generic workflow machinery comes from infrastructure/approvals.
2. The access/sync completion hand-off (SYNC_COMPLETED / SYNC_FAILED) that today advances the request via the in-process event bus is reclassified as a workflow step and delivered over the outbox / QueueService (TASK-34) — a durable step, not an event.
3. The operator-alert notification ('no approvers found') is rehomed onto the notifications capability (TASK-32), not the event bus.
4. Behavior is preserved end to end (submit -> approve -> grant, rejection, expiry, sync-driven advance).

Depends on the approvals capability extraction, the QueueService/outbox (TASK-34), and the notifications capability (TASK-32). The task-planner agent must assess feasibility as one PR vs decomposition into incremental subtasks that keep the live access flow green throughout.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 access/request supplies only access-specific ApprovalPolicy + EffectHandler; all generic workflow machinery comes from infrastructure/approvals
- [ ] #2 SYNC_COMPLETED/SYNC_FAILED advance is reclassified as a durable workflow step delivered over the outbox/QueueService, not the event bus
- [ ] #3 The 'no approvers found' operator alert is rehomed onto the notifications capability, not the event bus
- [ ] #4 Submit -> approve -> grant, rejection, expiry, and sync-driven advance all behave as before (tests green)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 No access-request logic flows through the in-process event dispatcher
- [ ] #2 PR references decisions/approvals.md
<!-- DOD:END -->
