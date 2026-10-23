---
id: TASK-147.6
title: Due action-item reminders as a scheduled job behind the flag
status: To Do
assignee: []
created_date: 2026-10-13 14:00
updated_date: '2026-10-23T17:35:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-147.3
references:
  - https://github.com/cds-snc/sre-bot/issues/1711
parent_task_id: TASK-147
priority: low
type: feature
ordinal: 375000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A background job, registered through the hookimpl with a lease, reminds owners of due and overdue action items, per the cadence in the design doc. Reminders query the action-item due index (TASK-147.2) with RecordQuery(index='due', partition the due bucket, sort lt now), never a table scan. Index reads may be eventually consistent, so the once-per-window guard does not depend on read-your-writes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Reminders are sent once per due window, safe to run twice, and only while the flag is on
<!-- AC:END -->
