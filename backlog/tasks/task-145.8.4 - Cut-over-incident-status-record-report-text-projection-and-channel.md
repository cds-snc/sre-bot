---
id: TASK-145.8.4
title: 'Cut over incident status: record, report text, projection and channel'
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-16T13:16:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.8.1
  - TASK-145.12.1
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.8
priority: medium
type: feature
ordinal: 509000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L6b. `incident status update` writes the record, the report status text, the projection and the channel in that order (named behaviour change: the legacy slash path never wrote the record); IncidentReport.set_status_text with the mapping moved from incident_document.py 55-80 into core/adapters/google_docs.py; incident_status.py deleted.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Status writes record, report, projection, channel in order, each failure logged and the rest continuing (tested; checks parent ACs #3, #9)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-16 (TASK-145.12.1 rulings): update_status upserts on the incident id (column F), so a missing row is written in full rather than reported NOT_FOUND; the order record -> report -> projection -> channel is unchanged; the legacy valid_statuses list is deleted here.
<!-- SECTION:NOTES:END -->
