---
id: TASK-147.2
title: >-
  Postmortem record and action-item store behind the incident postmortem-records
  flag, default off
status: To Do
assignee: []
created_date: 2026-10-13 14:00
updated_date: '2026-10-23T17:35:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.5
references:
  - https://github.com/cds-snc/sre-bot/issues/1707
parent_task_id: TASK-147
priority: high
type: feature
ordinal: 371000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
postmortem/ gains its domain (Postmortem with facts, the action items and the narrative snapshot; ActionItem with owner, priority, due date, status and an issue reference that carries its system) and a store over the records contract with an in-memory fake. The flag is one incident settings field, default off, following the access-management settings pattern, with its key false in app/config/base.toml and switched per environment file (decisions/configuration.md), never an environment variable; nothing user-facing reads the new records while it is off. Backend only: no surface, so it does not wait for the UX session.

Action items are their own records keyed (incident_id, item_id), with a sparse due GSI (partition due_bucket, sort due_at) declared in RecordTable.indexes and set only while an item is open; marking an item done removes both attributes. Edits and assignment are RecordStore.update set changes (TASK-27.2), and due items are read with RecordQuery(index='due') and a lt sort condition. This task owns the Terraform for the action-item table and its due index.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Postmortem and ActionItem are frozen dataclasses; the issue reference carries system and id, never a bare URL
- [ ] #2 The postmortem store runs over RecordStore with an in-memory fake exercising the same cases
- [ ] #3 The postmortem-records flag exists in the incident settings, default off, with its key false in app/config/base.toml and no environment-variable switch, and gates every surface added by TASK-147
<!-- AC:END -->
