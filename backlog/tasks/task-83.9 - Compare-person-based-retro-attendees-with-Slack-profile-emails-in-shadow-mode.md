---
id: TASK-83.9
title: Compare person-based retro attendees with Slack profile emails in shadow mode
status: To Do
assignee: []
created_date: 2026-09-10 16:18
updated_date: '2026-11-25T20:12:00Z'
labels:
  - identity
dependencies:
  - TASK-83.6
  - TASK-145
references:
  - app/modules/incident/schedule_retro.py
  - https://github.com/cds-snc/sre-bot/issues/1633
parent_task_id: TASK-83
priority: medium
ordinal: 176000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Updated 2026-09-24: decisions/migration.md rule 1 freezes modules/incident to bug fixes, so the person-based comparison and cutover cannot be added to modules/incident/schedule_retro.py. They run against the rebuilt retro surface in app/features/incident/ (TASK-145), which reaches attendees' calendars through the calendar capability or a feature adapter. The steps below still apply; read 'modules/incident/schedule_retro.py' as 'the rebuilt retro surface'.

modules/incident/schedule_retro.py resolves retro attendees from Slack profile emails. Before changing who gets invited, compute the attendee list from people (each attendee's calendar home account) alongside the current list, and log the differences. SRE can then see link coverage and mismatches without affecting invitations.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Scheduling a retro computes both attendee lists, and invitations still use the current Slack-email list
- [ ] #2 Differences (unlinked attendees, different addresses) are logged per retro with person and account ids, never emails
- [ ] #3 A setting disables the comparison
- [ ] #4 Existing retro scheduling tests stay green, and new tests cover linked, unlinked and mixed attendees
- [ ] #5 If app/bin/baselines/package_shape.txt still holds the people capability's readme-consumers entry, it is deleted and the capability README names this consumer
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-25T20:12:00Z

---

2026-11-25 (TASK-145.10.3 M2b plan, approved): the rebuilt retro surface resolves attendee emails through postmortem's AttendeeDirectory Protocol (incident/postmortem/interfaces.py, emails_for(conversation, account_ids)), implemented now by ConversationAttendeeDirectory over IncidentConversation.account_emails (Slack profile email, tolerated by people-and-accounts.md until TASK-83.6). The shadow comparison wraps that one adapter: person-based emails beside the conversation emails, mismatches logged.

---
<!-- COMMENTS:END -->
