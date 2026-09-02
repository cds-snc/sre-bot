---
id: TASK-25.1.6.9
title: Move modules incident Calendar and Meet call sites onto the incident adapter
status: To Do
assignee: []
created_date: '2026-09-02 15:03'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.7
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/google_calendar.py
  - app/integrations/google_workspace/meet.py
parent_task_id: TASK-25.1.6
priority: medium
ordinal: 140000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Smallest of the legacy-incident adapter slices; three call sites total. Follows TASK-25.1.6.7's boundary-placement decision.

CONSUMERS (grep-confirmed): modules/incident/schedule_retro.py calls google_calendar.get_freebusy and insert_event; modules/incident/core.py calls meet.create_space at two sites, both already inside the caller's own try/except.

SCOPE: the adapter builds stub-typed CalendarResource / MeetResource via get_calendar_service and get_meet_service, calls freebusy().query / events().insert / spaces().create directly, and does its own try/except + classify_google_error. modules/incident/schedule_retro.py and core.py call the adapter. integrations/google_workspace/google_calendar.py and meet.py are then deleted.

DEPENDENCY ON TASK-25.1.6.2: google_calendar.py's four pure helpers (find_first_available_slot, identify_unavailable_users, get_federal_holidays, get_utc_hour) must already have moved out of app/integrations/ before that file can be deleted. If TASK-25.1.6.2 has not landed, this slice cannot complete its deletion criterion - sequence accordingly rather than moving the helpers ad hoc here.

WATCH: core.py's existing try/except around create_space predates classification. Once the adapter classifies, decide whether that caller-side handling is still the right shape or whether it now duplicates the adapter's - and say which in the notes. Do not leave two overlapping error handlers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The incident adapter builds stub-typed CalendarResource and MeetResource via get_calendar_service/get_meet_service, calls freebusy().query, events().insert and spaces().create directly, and performs its own try/except + classify_google_error
- [ ] #2 modules/incident/schedule_retro.py and modules/incident/core.py call the adapter; neither imports integrations.google_workspace
- [ ] #3 app/integrations/google_workspace/google_calendar.py and meet.py are deleted with their test files, grep-verified zero references repo-wide outside backlog/ and tmp/ (requires TASK-25.1.6.2's helper relocation to have landed)
- [ ] #4 core.py's pre-existing try/except around create_space is either kept with a stated reason or removed as now-duplicated adapter handling; the choice is recorded in the notes and covered by a test
- [ ] #5 Existing test_schedule_retro.py, test_incident_core.py and test_meet.py coverage is preserved at the new boundary, including the delegated_user_email pass-through and HttpError propagation cases TASK-25.1.1 added
<!-- AC:END -->
