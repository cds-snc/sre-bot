---
id: TASK-147.6
title: Due action-item reminders as a scheduled job behind the flag
status: To Do
assignee: []
created_date: '2026-10-13 14:00'
labels:
  - incident
  - features
dependencies:
  - TASK-147.3
parent_task_id: TASK-147
priority: low
type: feature
ordinal: 375000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A background job, registered through the hookimpl with a lease, reminds owners of due and overdue action items, per the cadence in the design doc.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Reminders are sent once per due window, safe to run twice, and only while the flag is on
<!-- AC:END -->
