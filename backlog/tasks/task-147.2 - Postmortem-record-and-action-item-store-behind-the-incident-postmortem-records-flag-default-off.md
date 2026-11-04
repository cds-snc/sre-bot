---
id: TASK-147.2
title: >-
  Postmortem record and action-item store behind the incident postmortem-records
  flag, default off
status: To Do
assignee: []
created_date: 2026-10-13 14:00
updated_date: '2026-11-04T16:44:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.5
references:
  - https://github.com/cds-snc/sre-bot/issues/1707
  - .claude/skills/domain-model-evolution/SKILL.md
parent_task_id: TASK-147
priority: high
type: feature
ordinal: 371000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
postmortem/ gains its domain (Postmortem with facts, the narrative snapshot and the keys of its follow-up action items) and a store over the records contract with an in-memory fake. ActionItem is an incident record type, not a postmortem one (decisions/incident-management.md, amended 2026-11-04): the frozen dataclass and its store live in core/ behind core/api.py, with a kind (response or follow_up), owner, priority, due date, status and an issue reference that carries its system. Nothing postmortem-specific goes in the record, so response action items (TASK-165.4) and coordination's optional references (engagement, finding, repository, root incident id) are added later without changing existing items. This task writes follow_up items only. The flag is one incident settings field, default off, following the access-management settings pattern, with its key false in app/config/base.toml and switched per environment file (decisions/configuration.md), never an environment variable; nothing user-facing reads the new records while it is off. Backend only: no surface, so it does not wait for the UX session.

Action items are their own records keyed (incident_id, item_id), with a sparse due GSI (partition due_bucket, sort due_at) declared in RecordTable.indexes and set only while an item is open; the due bucket includes the kind, so each kind's reminder job reads only its own partitions. Marking an item done removes both attributes. Edits and assignment are RecordStore.update set changes (TASK-27.2), and due items are read with RecordQuery(index='due') and a lt sort condition. This task owns the Terraform for the shared action-item table and its due index.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Postmortem and ActionItem are frozen dataclasses; the issue reference carries system and id, never a bare URL
- [ ] #2 The postmortem store runs over RecordStore with an in-memory fake exercising the same cases
- [ ] #3 The postmortem-records flag exists in the incident settings, default off, with its key false in app/config/base.toml and no environment-variable switch, and gates every surface added by TASK-147
- [ ] #4 ActionItem and its store live in core/ behind core/api.py with a kind of response or follow_up; the record holds nothing postmortem-specific, the due bucket includes the kind, and postmortem/ writes follow_up items only
- [ ] #5 The approved plan records the shared action-item lifecycle, ownership and visibility invariants and scenario/cardinality evidence. Coordination-specific references are not required by this first delivery; the plan assigns migration and compatibility tests to the later tasks that introduce them.
<!-- AC:END -->
