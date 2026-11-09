---
id: TASK-145.12.1
title: Incident list projection adapter in core over integrations/google_workspace
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/workplace-systems.md
parent_task_id: TASK-145.12
priority: medium
type: feature
ordinal: 504000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L4c (approved program in TASK-145.7's plan, section 2; outline in TASK-145.12's plan). core/api.py IncidentListProjection (append_row, update_status), core/adapters/google_sheets.py over integrations/google_workspace, fake and parity test; row format copied from incident_folder.py:279 and :311. Inert until TASK-145.8's status cutover and the declare service register writers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The projection exposes only append_row and update_status and calls integrations/google_workspace directly; nothing in the incident umbrella uses infrastructure/spreadsheets (parent ACs #1 adapter part, #6)
- [ ] #2 Rows match the legacy writer's format (tested against the pinned values)
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
