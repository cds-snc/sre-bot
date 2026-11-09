---
id: TASK-145.8.3
title: Cut over incident show and the update modal
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.8.1
  - TASK-145.8.2
references:
  - decisions/incident-management.md
  - decisions/migration.md
parent_task_id: TASK-145.8
priority: medium
type: feature
ordinal: 508000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L6a (slices in TASK-145.8's plan). incident.response registers show and the update modal (modal-internal ids prefixed), reads through find_incident_for_conversation and writes through L3 in today's order; severity options stay none and SEV1-SEV4; security_incident editable. information_display.py and information_update.py deleted with their registrations; the field-update pins rewired to Protocol fakes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The show and update pins pass with assertions unchanged, fixtures rewired; information_display.py and information_update.py are gone (checks parent ACs #1, #4, #6 and the show part of #5)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
