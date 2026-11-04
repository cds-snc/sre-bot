---
id: TASK-147.5
title: Action-item status sync from GitHub through the webhooks capability
status: To Do
assignee: []
created_date: 2026-10-13 14:00
updated_date: '2026-11-04T16:10:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-147.4
  - TASK-37
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
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Closing or reopening the linked issue updates the action item's status
- [ ] #2 The sync updates response and follow_up items alike and holds no kind-specific logic
<!-- AC:END -->
