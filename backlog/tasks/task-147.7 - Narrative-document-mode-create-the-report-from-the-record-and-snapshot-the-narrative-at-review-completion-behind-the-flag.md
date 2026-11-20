---
id: TASK-147.7
title: >-
  Narrative document mode: create the report from the record and snapshot the
  narrative at review completion, behind the flag
status: To Do
assignee: []
created_date: 2026-10-13 14:00
updated_date: '2026-11-20T22:05:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-147.2
  - TASK-145.6
  - TASK-145.11
references:
  - https://github.com/cds-snc/sre-bot/issues/1712
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

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-20T22:05:00Z

---

2026-11-20 (human, TASK-145.10 program-scope rulings): 'review complete' is the incident's move to Reviewed (IncidentStatus READY_TO_BE_REVIEWED -> REVIEWED), made by a person; a held meeting changes no status. Raise it through a status-changed extension point in common/ (incident-management.md:56) that postmortem/ listens to for the snapshot.

---
<!-- COMMENTS:END -->
