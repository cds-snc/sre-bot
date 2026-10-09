---
id: TASK-145.10
title: >-
  Build incident/postmortem: schedule the postmortem meeting over the calendar
  capability
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.6
  - TASK-138
  - TASK-36.1
parent_task_id: TASK-145
priority: medium
type: feature
ordinal: 360000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer D1 of TASK-145: plugin incident.postmortem, independent of the response slices after TASK-145.6. Rebuilds schedule_retro (the modal flow, the schedule button from the nudge, availability search and meeting creation). A postmortem meeting is a meeting about the incident: calendar operations come from the calendar capability (TASK-138), so this subdomain has no calendar adapter.

THIS SLICE
- postmortem/entrypoints/slack.py and slack_views.py: the modal and the schedule action id declared in common/vocabulary.
- postmortem/service.py: resolve the incident through find_incident_for_conversation; attendees from channel members as today; availability and meeting creation through capabilities.calendar.api; store the PostmortemMeetingReference (system, tenant, event id, link) on the record; post the confirmation when the conversation is writable.
- Behaviour-preserving: pick a day offset and attendees, first free slot, one meeting. Rescheduling, cancelling, action items and feedback are expansions.
- User-facing labels keep today's "retro" wording in the catalogues; the code and the record say postmortem.
- Legacy registration removed in the same PR; modal fields and replies unchanged, pinned by TASK-36.1.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/incident/postmortem/ is registered as incident.postmortem and handles the schedule modal and the nudge's schedule button
- [ ] #2 Meeting availability and creation go through capabilities.calendar.api; postmortem/ has no adapters/ directory
- [ ] #3 The meeting reference is stored on the record with system, tenant and event id
- [ ] #4 The pinned schedule flow passes unchanged
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
