---
id: TASK-147.3
title: 'Action items from Slack: add, confirm, edit, assign and list, behind the flag'
status: To Do
assignee: []
created_date: 2026-10-13 14:00
updated_date: '2026-10-23T17:35:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-147.1
  - TASK-147.2
  - TASK-27.2
references:
  - https://github.com/cds-snc/sre-bot/issues/1708
parent_task_id: TASK-147
priority: medium
type: feature
ordinal: 372000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Slack surfaces decided by the UX session (TASK-147.1) over the action-item store, registered only when the flag is on. Includes reviewing action items the AI proposes from the transcript. Teams follows the platform work. Edit and assign are RecordStore.update set changes (TASK-27.2); closing or marking an item done removes the due-index attributes (due_bucket, due_at, TASK-147.2) in the same update call.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With the flag off no action-item surface is registered and today's doc table is untouched
- [ ] #2 With the flag on, action items can be added, confirmed, edited, assigned and listed per the design doc, in EN and FR
<!-- AC:END -->
