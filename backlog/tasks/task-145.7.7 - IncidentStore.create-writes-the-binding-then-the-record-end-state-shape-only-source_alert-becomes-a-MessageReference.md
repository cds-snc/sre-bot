---
id: TASK-145.7.7
title: >-
  IncidentStore.create writes the binding then the record, end-state shape only;
  source_alert becomes a MessageReference
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-09T21:17:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.7.3
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 505000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L5 (approved program in TASK-145.7's plan, section 2; outline in the parent plan). IncidentStore.create(incident, binding): binding put, then record put (both put_if_not_exists; the record is the commit point); set_reference(incident_id, kind, reference) guarded on record_version; the item carries only end-state names plus channel_id, record_version 2, open_bucket and opened_at in the same put; MessageReference gains url and replaces SourceAlertReference. Inert until L9a.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 create writes the binding before the record; a replay is a no-op; a record failure leaves a dangling binding that the lookup ignores, and a retry with a new incident id resolves to the new incident, not AMBIGUOUS (tested)
- [ ] #2 The created item holds only end-state attribute names plus channel_id, record_version 2, open_bucket and opened_at from format_stored_time (width and offset tested) (checks parent ACs #5, #7)
- [ ] #3 SourceAlertReference is deleted; source_alert is a MessageReference with an optional url (checks the shape part of parent AC #6)
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (TASK-145.7.3 approval, R1): AC #1 gains the retry case: a crashed declare leaves a dangling binding, a retry with a new incident id adds a live one on the same conversation; the lookup drops the dangling one before the ambiguity rule (incident-management.md :34, revised in 145.7.3). The plan states whether the retry reuses the incident id.
<!-- SECTION:NOTES:END -->
