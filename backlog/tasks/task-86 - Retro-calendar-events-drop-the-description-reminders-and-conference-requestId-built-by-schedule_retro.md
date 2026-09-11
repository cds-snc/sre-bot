---
id: TASK-86
title: >-
  Retro calendar events drop the description, reminders and conference requestId
  built by schedule_retro
status: To Do
assignee: []
created_date: '2026-09-10 17:48'
updated_date: '2026-09-11 14:13'
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
and calls insert_event(..., **event_config). packages/incident/scheduling/adapters/google_calendar.py::insert_event accepts **kwargs but only pops delegated_user_email; it never merges the other keys into the events.insert body. Retro events are therefore very likely created with no description and default reminders, and with the adapter's random requestId (generate_unique_id) instead of the caller's timestamp-based one. Nothing fails: the keys are dropped silently.

PRE-EXISTING: the legacy integrations/google_workspace/google_calendar.py::insert_event had the identical shape, so the TASK-25.1.6.9 migration carried this across verbatim rather than introducing it. Existing adapter tests never pass description or reminders, so they cannot catch it. Check whether the schedule_retro tests assert on the kwargs handed to insert_event.

DECIDE WHEN PLANNING:
- The intended event body: description and reminder override are presumably wanted, since the caller builds them deliberately.
- Explicit typed parameters on insert_event rather than a **kwargs body passthrough.
- One requestId source. The caller's value is deterministic per slot; the adapter's is random. conferenceData.createRequest.requestId dedups only the conference creation, not the event itself, so it does not make events.insert replay-safe on its own. Verify the requestId semantics against the Calendar API docs rather than recall. Prefer the deterministic per-slot value: TASK-87 plans to derive a client-supplied event id from the same per-slot key so there is one idempotency source, not two.

COORDINATION (updated 2026-09-11):
- TASK-25.1.6.11.3 is Done: generate_unique_id now lives in this adapter and body_kwargs is gone. Plan against the current file.
- TASK-25.1.6.16 (stopgap, under TASK-25.1.6) adds num_retries=0 to the same events().insert(...).execute() call in insert_event, because construction-time retry made a replay re-send invitations. Whichever lands second rebases; keep that argument on the call when reshaping insert_event.
- TASK-87 (deferred) owns the lasting replay-safety design for this write (deterministic event id, 409 duplicate as success) and replaces the archived TASK-25.1.6.15. Do not add a client-supplied event id here; keep this task to the dropped fields and the requestId source.
- decisions/migration.md permits bug fixes inside frozen app/modules.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A retro event created through schedule_retro sends the description and the 10-minute popup reminder override in the events.insert body, proven by a test asserting the body passed to events().insert
- [ ] #2 conferenceData.createRequest.requestId has exactly one source, and the unused duplicate is removed from either schedule_retro.py or the adapter
- [ ] #3 insert_event takes the event fields it supports as explicit parameters; unsupported keyword arguments are rejected rather than silently ignored
- [ ] #4 The new tests fail against the pre-fix code (recorded in the notes), and ruff, mypy and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
