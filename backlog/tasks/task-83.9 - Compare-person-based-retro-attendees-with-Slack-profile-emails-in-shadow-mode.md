---
id: TASK-83.9
title: Compare person-based retro attendees with Slack profile emails in shadow mode
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
dependencies:
  - TASK-83.7
references:
  - app/modules/incident/schedule_retro.py
parent_task_id: TASK-83
priority: medium
ordinal: 176000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
modules/incident/schedule_retro.py resolves retro attendees from Slack profile emails. Before changing who gets invited, compute the attendee list from people (each attendee's calendar home account) alongside the current list, and log the differences. SRE can then see link coverage and mismatches without affecting invitations.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Scheduling a retro computes both attendee lists, and invitations still use the current Slack-email list
- [ ] #2 Differences (unlinked attendees, different addresses) are logged per retro with person and account ids, never emails
- [ ] #3 A setting disables the comparison
- [ ] #4 Existing retro scheduling tests stay green, and new tests cover linked, unlinked and mixed attendees
<!-- AC:END -->
