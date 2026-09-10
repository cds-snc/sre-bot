---
id: TASK-86
title: >-
  Retro calendar events drop the description, reminders and conference requestId
  built by schedule_retro
status: To Do
assignee: []
created_date: '2026-09-10 17:48'
labels:
  - incident
  - bug
dependencies: []
references:
  - app/modules/incident/schedule_retro.py
  - app/packages/incident/scheduling/adapters/google_calendar.py
  - >-
    https://developers.google.com/workspace/calendar/api/v3/reference/events/insert
priority: high
type: bug
ordinal: 185000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
BUG (found 2026-09-10 by code reading while planning TASK-25.1.6.11; confirm against a real created event before fixing).

WHAT HAPPENS: modules/incident/schedule_retro.py:321-345 builds
  event_config = {description, conferenceData.createRequest {requestId: str(first_available_start.timestamp()), conferenceSolutionKey hangoutsMeet}, reminders {useDefault: False, overrides: [popup 10 min]}}
and calls insert_event(..., **event_config). packages/incident/scheduling/adapters/google_calendar.py::insert_event (:44-123) accepts **kwargs but only pops delegated_user_email (:94); it never merges the other keys into the events.insert body (:64-90). Retro events are therefore very likely created with no description and default reminders, and with the adapter's random requestId (generate_unique_id, :73) instead of the caller's timestamp-based one. Nothing fails: the keys are dropped silently.

PRE-EXISTING: the legacy integrations/google_workspace/google_calendar.py::insert_event had the identical shape, so the TASK-25.1.6.9 migration carried this across verbatim rather than introducing it. Existing adapter tests never pass description or reminders, so they cannot catch it. Check whether the schedule_retro tests assert on the kwargs handed to insert_event.

DECIDE WHEN PLANNING:
- The intended event body: description and reminder override are presumably wanted, since the caller builds them deliberately.
- Explicit typed parameters on insert_event rather than a **kwargs body passthrough.
- One requestId source. The caller's value is deterministic per slot; the adapter's is random. conferenceData.createRequest.requestId semantics affect replay safety, so coordinate with TASK-25.1.6.15, which owns SDK-replay safety for this exact events.insert. Verify the requestId semantics against the Calendar API docs rather than recall.

COORDINATION: TASK-25.1.6.11.3 moves generate_unique_id into this adapter and removes its unused body_kwargs parameter. Whichever lands second rebases. decisions/migration.md permits bug fixes inside frozen app/modules.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A retro event created through schedule_retro sends the description and the 10-minute popup reminder override in the events.insert body, proven by a test asserting the body passed to events().insert
- [ ] #2 conferenceData.createRequest.requestId has exactly one source, and the unused duplicate is removed from either schedule_retro.py or the adapter
- [ ] #3 insert_event takes the event fields it supports as explicit parameters; unsupported keyword arguments are rejected rather than silently ignored
- [ ] #4 The new tests fail against the pre-fix code (recorded in the notes), and ruff, mypy and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
