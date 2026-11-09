---
id: TASK-145.8.1
title: >-
  Core incident updates: guarded fields, roles, close, reopen, upgrade-on-write
  and severity timeline entries
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.7.4
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.8
priority: medium
type: feature
ordinal: 506000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L3 (approved program in TASK-145.7's plan, section 2; slices in TASK-145.8's plan). IncidentStore gains update_fields, set_roles, close and reopen through upgrade-on-write (plan section 3), and the timeline store (timeline_table, entry_key, ids) with a severity_changed system entry written after the field update. Inert until the cutovers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Guarded update, lost guard (one re-read and retry, then a classified conflict), upgrade-on-write in one pass (binding + marker 2), unreadable legacy item refused with the field named, close/reopen bucket rules, replay of the same change (tested; checks parent AC #7 and the upgrade-on-write AC)
- [ ] #2 A severity change appends one timeline entry with a deterministic id after the field update; a failed entry never rolls the field back (tested; checks the severity AC)
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
