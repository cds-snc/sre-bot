---
id: TASK-147.7
title: >-
  Narrative document mode: create the report from the record and snapshot the
  narrative at review completion, behind the flag
status: To Do
assignee: []
created_date: '2026-10-13 14:00'
labels:
  - incident
  - features
dependencies:
  - TASK-147.2
  - TASK-145.6
  - TASK-145.11
parent_task_id: TASK-147
priority: medium
type: feature
ordinal: 376000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
With the flag on, the report document is created from the record with the facts and action items rendered as read-only context, the AI draft writes proposals to the record instead of into the doc, and marking the review complete stores a snapshot of the narrative in the record. With the flag off, today's document behaviour is unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With the flag on, the document is created from the record and the narrative snapshot is stored at review completion
- [ ] #2 With the flag off, document creation, the timeline section, the action-items table and the draft behave as today
<!-- AC:END -->
