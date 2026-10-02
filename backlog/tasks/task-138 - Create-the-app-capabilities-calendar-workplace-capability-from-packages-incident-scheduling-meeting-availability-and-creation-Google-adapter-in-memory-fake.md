---
id: TASK-138
title: >-
  Create the app/capabilities/calendar/ workplace capability from
  packages/incident/scheduling: meeting availability and creation, Google
  adapter, in-memory fake
status: To Do
assignee: []
created_date: '2026-10-02 16:59'
labels:
  - plugin-architecture
  - capabilities
  - workplace-systems
milestone: m-7
dependencies:
  - TASK-110
  - TASK-114
references:
  - decisions/workplace-systems.md
  - decisions/incident-management.md
  - decisions/plugin-architecture.md
  - decisions/outbound-clients.md
priority: medium
ordinal: 314000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/workplace-systems.md: calendar is a workplace capability, not infrastructure and not incident code. decisions/incident-management.md (2026-10-02): a retrospective is a meeting that happens to be about an incident, so meeting scheduling lives in app/capabilities/calendar/ and the incident retrospective subdomain consumes it.

TODAY: packages/incident/scheduling/ holds adapters/google_calendar.py (freebusy, events.insert) and availability.py (first free slot in a window), consumed by modules/incident/schedule_retro.py. TASK-86 (dropped description, reminders and conference request id) and TASK-87.3 (replay-safe events.insert) are open against that adapter.

SCOPE (behaviour-preserving; plugin-architecture.md capability tests: incident needs it now, it carries organization policy across suites, its vocabulary is feature-free)
- app/capabilities/calendar/ in the feature-packages shape: api.py (MeetingScheduler interface, Meeting, Attendee, AvailabilityWindow, MeetingReference carrying system, tenant, event id and the vendor link; provider function), domain.py (availability logic moved from availability.py), adapters/google.py (the only file importing integrations.google_workspace; try/except plus classify; typed parameters, so description, reminders and the conference request reach the event: fixes TASK-86 in the touched file), an in-memory fake, settings.py, README.md with its classification and the incident consumer named.
- Operations: find availability for attendees over a window; create a meeting with a conference link. Update, reschedule and cancel are NOT built here (Path A capabilities are not built speculatively); DRAFT-8 adds them with their first consumer.
- Which system applies is data: the person's calendar home or the stored MeetingReference (workplace-systems.md rule 3), never a setting; with one Google tenant today the adapter is the only one.
- modules/incident/schedule_retro.py and packages/incident/scheduling consumers are repointed to capabilities.calendar.api (migration.md rule 5: an import-path change in a frozen module); packages/incident/scheduling is deleted; the incident umbrella layers contract drops it.
- No vocabulary from incident (retro, incident, channel) appears in the capability.

Sequencing: Wave 4 capability move like TASK-119 to TASK-121, after TASK-110 and TASK-114. TASK-38.6 depends on it. TASK-124.5 moves the incident umbrella without scheduling if this lands first, with it otherwise.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/calendar/api.py exposes MeetingScheduler, Meeting, Attendee, AvailabilityWindow, MeetingReference (system, tenant, event id, vendor link) and a provider; no incident, retro or channel vocabulary appears in the package
- [ ] #2 The Google adapter is the only file importing integrations.google_workspace, has typed parameters, sends description, reminders and the conference request, classifies errors and returns OperationResult; the in-memory fake passes the same contract tests
- [ ] #3 packages/incident/scheduling no longer exists; modules/incident/schedule_retro.py imports capabilities.calendar.api only; the TASK-36.1 retro pinning tests are green with no assertion change
- [ ] #4 README states the classification and names the incident consumer; the capability has an entry point and an enablement key; no new import-linter ignore entry
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
