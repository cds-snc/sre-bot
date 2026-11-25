---
id: TASK-37.6
title: 'Webhooks slice 6: management plane (coordinator of 37.6.1 and 37.6.2)'
status: To Do
assignee: []
created_date: '2026-11-25T20:48:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.2.2
  - TASK-37.4.1
references:
  - decisions/webhooks.md
  - decisions/managed-content.md
  - decisions/authorization.md
parent_task_id: TASK-37
priority: high
ordinal: 546000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Coordinator only. Do not write production code against this task; pick up a child.

The webhooks control plane (decisions/webhooks.md Two planes; managed-content.md one write path; TASK-168 research packet Q10). A WebhookAdmin service is the only writer of webhook instances, behind the webhooks:admin permission (authorization.md, deny by default), with every write audited (AU-3). API first (/api/v1/webhooks); /sre webhooks becomes one Slack binding over the same service, and Backstage can be another. Replaces the legacy admin in modules/slack/webhooks*.py and modules/sre/webhook_helper.py, which has no permission check today.

Children:
- TASK-37.6.1 Management service and API (prod: new authenticated routes). Runs in parallel with the data-plane cutover once TASK-37.2.2 and TASK-37.4.1 are in.
- TASK-37.6.2 Slack binding over the service; deletes the legacy admin (prod: Slack UI). After TASK-37.5.

The old single "admin surface" slice is split so that TASK-47's issuance and TASK-48's owner notices build on 37.6.1 before the legacy admin is deleted. TASK-40 no longer owns the webhook CRUD and admin views (OQ9).

Dependencies: the coordinator carries its first child's dependencies (TASK-145.5 and 145.10 precedent).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 TASK-37.6.1 and TASK-37.6.2 are Done
- [ ] #2 Webhook instances are written only through the WebhookAdmin service; no other writer remains (grep)
<!-- AC:END -->
