---
id: DRAFT-8
title: >-
  Retro meeting management: reschedule, modify, cancel and change attendees of
  the retrospective, with reminders, through the calendar capability
status: Draft
assignee: []
created_date: '2026-10-02 16:59'
labels:
  - incident
  - later-wave
dependencies:
  - TASK-38.6
  - TASK-138
references:
  - decisions/incident-management.md
parent_task_id: TASK-97
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EXPANSION (after doc-2). Today the retro flow creates one meeting and stops: nothing in the bot can move, modify or cancel it, change attendees, or remind people, so every change is manual in the calendar and the record's retrospective link goes stale. This task completes the retro portion of the incident workflow:
- the calendar capability gains update, reschedule and cancel operations and attendee changes with this task as their first consumer (Path A capabilities are never built speculatively);
- retrospective/ gains the matching use cases over the record's RetrospectiveReference (one subdomain: these are switched on together with scheduling), plus a reminder before the retro and a nudge when a closed incident has no retro;
- attendees come from people (TASK-83.10) with the explicit fallback.
EN and FR; every link rendered by the owning adapter.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Reschedule, modify, cancel and attendee changes exist as retrospective use cases over the stored RetrospectiveReference, through capabilities.calendar.api only
- [ ] #2 The calendar capability's new operations land with this consumer and are covered by the Google adapter and the in-memory fake
- [ ] #3 A reminder before the retro and a nudge for a closed incident without a retro are Tier-2 jobs safe to run twice
<!-- AC:END -->
