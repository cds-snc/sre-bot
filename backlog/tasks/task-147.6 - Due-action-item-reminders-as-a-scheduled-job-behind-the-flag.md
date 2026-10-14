---
id: TASK-147.6
title: Due action-item reminders as a scheduled job behind the flag
status: To Do
assignee: []
created_date: '2026-10-13 14:00'
updated_date: '2026-10-13 19:59'
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

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-13 19:59
---
2026-10-13 records/incidents layout decision: reminders query the action-item due index (TASK-147.2) with RecordQuery(index='due', partition=due bucket, sort lt now); no table scan. Index reads may be eventually consistent, so the once-per-window guard must not depend on read-your-writes.
---
<!-- COMMENTS:END -->
