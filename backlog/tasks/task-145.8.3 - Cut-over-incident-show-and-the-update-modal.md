---
id: TASK-145.8.3
title: Cut over incident show and the update modal
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T21:00:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.8.1
  - TASK-145.8.2
  - TASK-145.8.7
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
- [ ] #3 The PR body states the revert target: one git revert restores the legacy surface, and the L5r rollback guard (TASK-145.8.2) keeps it reading and writing upgraded items correctly (decisions/incident-management.md Migration rule 1)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 (human ruling at TASK-145.8.1 planning): the Retro Link (retrospective_url) is dropped from show and the update modal: named behaviour change in the PR body; the field-update pin (tests/integration/legacy_surface/test_incident_field_update_surface.py:95-96, :127, :134) is updated to match. The record holds typed references only (decisions/incident-management.md:32); legacy values stay on items (Migration rule 5); TASK-145.10's postmortem_meeting reference replaces it. Severity changes go through IncidentStore.update_fields(changes, by, at), which writes the severity_changed timeline entry; status through set_status(status, at).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-10T21:00:00Z

---

2026-11-10 (human-approved, TASK-145.7.6 OQ3 R3): depends on TASK-145.8.7 (L3b, async incident core ports), stacked between L3 and this layer; plan this cutover against the async ports.

---
<!-- COMMENTS:END -->
