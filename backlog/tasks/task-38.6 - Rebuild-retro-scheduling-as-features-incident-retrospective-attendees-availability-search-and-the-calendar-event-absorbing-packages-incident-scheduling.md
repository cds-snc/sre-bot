---
id: TASK-38.6
title: >-
  Rebuild retro scheduling as features/incident/retrospective over the calendar
  capability: attendees, availability search and the retro meeting
status: To Do
assignee: []
created_date: '2026-10-02 16:43'
updated_date: '2026-10-02 16:59'
labels:
  - migration
  - phase-5
  - incident
milestone: m-5
dependencies:
  - TASK-38.2
  - TASK-36.1
  - TASK-138
references:
  - decisions/incident-management.md
  - decisions/feature-packages.md
  - decisions/migration.md
  - decisions/people-and-accounts.md
  - decisions/workplace-systems.md
parent_task_id: TASK-38
priority: medium
ordinal: 311000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 6 of TASK-38 (migrate). Rebuilds schedule_retro (the view_save_event modal flow, the schedule-retro button from the nudge, availability search and meeting creation) as features/incident/retrospective/ (entry point incident.retrospective), independently of the lifecycle slices. A retrospective is a meeting about the incident: calendar operations come from the calendar capability (decisions/incident-management.md; the capability task is a dependency), so this subdomain has no calendar adapter of its own.

THIS SLICE
- retrospective/entrypoints/slack.py: the modal and the schedule-retro action id declared in common/vocabulary.
- retrospective/service.py: resolve the incident through find_incident_for_conversation; attendees from channel members as today (TASK-83.9 and TASK-83.10 move this to people); availability and meeting creation through capabilities.calendar.api; store a RetrospectiveReference (wrapping the capability's MeetingReference: system, tenant, event id, vendor link) on the record; post the confirmation when the conversation is writable.
- Behaviour-preserving: today's flow only (pick a day offset and attendees, first free slot, one meeting). Rescheduling, modifying, cancelling and attendee changes are DRAFT-8, after doc-2; retro action items as records are DRAFT-9.
- Legacy registration removed in the same PR; modal fields and replies unchanged, pinned by TASK-36.1.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The retro flow is handled by features/incident/retrospective with one service call per handler; the schedule-retro action id is registered here and rendered by lifecycle through common/vocabulary; no import crosses the two subdomains
- [ ] #2 Availability and meeting creation go through capabilities.calendar.api; features/incident/retrospective/ has no adapters/ directory and imports no integrations module
- [ ] #3 A RetrospectiveReference with system, tenant, event id and the vendor link is stored on the record and rendered in the show modal
- [ ] #4 The incident umbrella layers contract lists lifecycle | retrospective | scribe above core above common
- [ ] #5 The TASK-36.1 pinning tests for the retro surfaces are green before and after the cutover with no assertion change
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; no baseline grew
<!-- AC:END -->
