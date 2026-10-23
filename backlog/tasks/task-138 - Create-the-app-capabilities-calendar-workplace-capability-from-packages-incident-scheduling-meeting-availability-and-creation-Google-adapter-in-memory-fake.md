---
id: TASK-138
title: >-
  Create the app/capabilities/calendar/ workplace capability from
  packages/incident/scheduling: meeting availability and creation, Google
  adapter, in-memory fake
status: To Do
assignee: []
created_date: 2026-10-02 16:59
updated_date: '2026-10-23T17:12:00Z'
labels:
  - plugin-architecture
  - capabilities
  - workplace-systems
milestone: m-7
dependencies:
  - TASK-110
  - TASK-114
  - TASK-36.1.2
references:
  - decisions/workplace-systems.md
  - decisions/incident-management.md
  - decisions/plugin-architecture.md
  - decisions/outbound-clients.md
  - https://github.com/cds-snc/sre-bot/issues/1681
priority: medium
ordinal: 314000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/workplace-systems.md: calendar is a workplace capability, not infrastructure and not incident code. decisions/incident-management.md: a postmortem meeting is a meeting about the incident, so meeting scheduling lives in app/capabilities/calendar/ and the incident postmortem subdomain (TASK-145.10) consumes it.

TODAY: features/incident/scheduling/ holds adapters/google_calendar.py (get_freebusy, insert_event) and availability.py (first free slot in a window, holidays, unavailable users), consumed by modules/incident/schedule_retro.py (lines 7 and 11). TASK-86 (dropped description, reminders and conference request id) and TASK-87.3 (replay-safe events.insert) are open against that adapter.

SCOPE (behaviour-preserving; plugin-architecture.md capability tests: incident needs it now, it carries organization policy across suites, its vocabulary is feature-free)
- app/capabilities/calendar/ in the feature-packages shape: api.py (MeetingScheduler interface, Meeting, Attendee, AvailabilityWindow, MeetingReference carrying system, tenant, event id and the vendor link; provider function), domain.py (availability logic moved from availability.py), adapters/google.py (the only file importing integrations.google_workspace; try/except plus classify; typed parameters, so description, reminders and the conference request reach the event: fixes TASK-86 in the touched file), an in-memory fake, settings.py, README.md with its classification and the incident consumer named.
- Operations: find availability for attendees over a window; create a meeting with a conference link. Update, reschedule and cancel are NOT built here (Path A capabilities are not built speculatively); DRAFT-8 adds them with their first consumer.
- Which system applies is data: the person's calendar home or the stored MeetingReference (workplace-systems.md rule 3), never a setting; with one Google tenant today the adapter is the only one. The calendar id schedule_retro.py reads from [google_resources] (sre_calendar_id) stays with the caller.
- modules/incident/schedule_retro.py and the features/incident/scheduling tests are repointed to capabilities.calendar.api (migration.md rule 5: an import-path change in a frozen module); features/incident/scheduling is deleted and the incident umbrella independence contract drops it (app/pyproject.toml:372).
- No vocabulary from incident (retro, incident, channel) appears in the capability.

Sequencing: a workplace capability move like TASK-119 to TASK-121, after TASK-114. TASK-145.10 depends on it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/calendar/api.py exposes MeetingScheduler, Meeting, Attendee, AvailabilityWindow, MeetingReference (system, tenant, event id, vendor link) and a provider; no incident, retro or channel vocabulary appears in the package
- [ ] #2 The Google adapter is the only file importing integrations.google_workspace, has typed parameters, sends description, reminders and the conference request, classifies errors and returns OperationResult; the in-memory fake passes the same contract tests
- [ ] #3 features/incident/scheduling no longer exists and the umbrella contract no longer lists it; modules/incident/schedule_retro.py imports capabilities.calendar.api only; the TASK-36.1.2 retro pinning tests (view_save_event, confirm_click, user_select_action) are green with no assertion change
- [ ] #4 README states the classification and names the incident consumer; the capability has an entry point and an enablement key; if it is the first package under app/capabilities/, the same PR adds capabilities to the import-linter root_packages; no new import-linter ignore entry
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
