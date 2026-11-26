---
id: TASK-147.5
title: Action-item status sync from GitHub through the webhooks capability
status: To Do
assignee: []
created_date: 2026-10-13 14:00
updated_date: '2026-11-26T19:07:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-147.4
  - TASK-37.4.3
  - TASK-37.2.3
references:
  - https://github.com/cds-snc/sre-bot/issues/1710
parent_task_id: TASK-147
priority: low
type: feature
ordinal: 374000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Issue state changes reach the action item as re-read hints through the webhooks capability, for an action item of either kind (response or follow_up), since both share the core/ store and tracker adapter. core/ registers no handlers (decisions/feature-packages.md), so postmortem/, which ships first, registers the one handler; it updates the item through core/api.py whatever its kind, and response/ (TASK-165.4) adds no second handler. Without it, status is kept in the app only.

Webhook path (2026-11-25, TASK-168 re-cut; decisions/webhooks.md): GitHub deliveries arrive through a github protocol built in this task as its first consumer (X-Hub-Signature-256 verified against the raw body; X-GitHub-Delivery is the delivery id for the inbox dedupe). The handler treats a delivery as a hint and fetches the issue's current state through the GitHub App rather than trusting payload fields (OWASP webhook guidance; thin events). It registers through the webhooks event-consumer hookspec (TASK-37.2.1), and the delivery reaches it once the capability serves the route (TASK-37.4.3).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Closing or reopening the linked issue updates the action item's status
- [ ] #2 The sync updates response and follow_up items alike and holds no kind-specific logic
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-25T20:53:00Z

---

2026-11-25 (TASK-168 re-cut, human-approved): dependency TASK-37 (the old umbrella) replaced by TASK-37.4.3 (the capability serves the webhook route) and TASK-37.2.1 (the event-consumer hookspec); TASK-147.4 kept. Description gains the github protocol and fetch-don't-trust (TASK-168 packet section 7.2, Q9).

---
<!-- COMMENTS:END -->
