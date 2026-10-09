---
id: TASK-145.10
title: >-
  Build incident/postmortem: schedule the postmortem meeting over the calendar
  capability
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 18:22'
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Outline plan grounded at main d2d973ae (2026-10-09); re-ground at pickup (after TASK-145.6, TASK-138 and TASK-36.1).

## Discovered state
- modules/incident/schedule_retro.py (389): open_incident_retro_modal (67), view_save_event submission -> handle_schedule_retro_submit, confirm_click and user_select_action (incident_helper.py 158-160); calendar through packages.incident.scheduling (schedule_event 26, 241; availability 14), which TASK-138 turns into capabilities/calendar. Attendees come from channel members. The retrospective_url is written to the legacy item.
- Not yet pinned (TASK-36.1).

## Steps
1. features/incident/postmortem/: __init__.py (hookimpls), settings.py (day offset default, meeting length), service.py schedule_meeting(incident, attendees, day_offset): availability and creation through capabilities.calendar.api, PostmortemMeetingReference written through IncidentStore.update_field, confirmation posted through IncidentConversation when writable; domain.py (attendee selection types).
2. postmortem/entrypoints: /sre incident schedule under sre.incident, the modal (view_save_event -> incident.postmortem.schedule.save), confirm_click and user_select_action under incident.postmortem.* ids; the nudge's schedule button id comes from common/vocabulary (rendered by response, handled here). Views and locales (keys moved from app/locales/incident.*.yml; labels keep "retro" wording pending decision).
3. Legacy schedule_retro.py registrations removed in the same PR; pinned by TASK-36.1.

## AC traceability
AC1: steps 1-2 -> registration test (modal and nudge button id). AC2: step 1 -> service tests with the calendar capability fake; `ls features/incident/postmortem` shows no adapters/. AC3: step 1 -> store update test (reference with system, tenant, event id). AC4: pinned flow green. AC5: gates.

## Test matrix
Schedule: first free slot found -> meeting created, reference stored, confirmation posted; no slot -> notice, nothing stored; archived channel -> stored without post; calendar failure classified. Attendee picker: channel members listed, selection kept across confirm.

## Assumptions and doubts
- capabilities.calendar.api shape per TASK-138 (MeetingScheduler, MeetingReference); confirm before coding.
- Whether labels switch from "retro" to "postmortem" is open question 2 in the delivery plan.

## Size
About 300 production lines. Under the gate.

## Blast radius and rollback
One modal flow; revert restores the legacy registration.
<!-- SECTION:PLAN:END -->
