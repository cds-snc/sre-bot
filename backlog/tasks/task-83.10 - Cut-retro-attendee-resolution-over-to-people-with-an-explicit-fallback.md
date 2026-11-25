---
id: TASK-83.10
title: Cut retro attendee resolution over to people with an explicit fallback
status: To Do
assignee: []
created_date: 2026-09-10 16:18
updated_date: '2026-11-25T20:12:00Z'
labels:
  - identity
dependencies:
  - TASK-83.9
  - TASK-145
references:
  - app/modules/incident/schedule_retro.py
  - https://github.com/cds-snc/sre-bot/issues/1620
parent_task_id: TASK-83
priority: medium
ordinal: 177000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Updated 2026-09-24: decisions/migration.md rule 1 freezes modules/incident to bug fixes, so the person-based comparison and cutover cannot be added to modules/incident/schedule_retro.py. They run against the rebuilt retro surface in app/features/incident/ (TASK-145), which reaches attendees' calendars through the calendar capability or a feature adapter. The steps below still apply; read 'modules/incident/schedule_retro.py' as 'the rebuilt retro surface'.

After SRE reviews the shadow comparison, retro invitations use each attendee's calendar home from people. Attendees without a link fall back to their Slack profile email, visibly, so nobody silently drops off an invitation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Linked attendees are invited through their calendar home account
- [ ] #2 Unlinked attendees fall back to their Slack profile email, with a warning log and a list SRE can act on
- [ ] #3 A setting restores the previous behavior
- [ ] #4 Tests cover linked, unlinked and mixed attendee sets
- [ ] #5 Full test suite, ruff and mypy pass
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-25T20:12:00Z

---

2026-11-25 (TASK-145.10.3 M2b plan, approved): the cutover swaps postmortem's AttendeeDirectory adapter (incident/postmortem/adapters/attendees.py, ConversationAttendeeDirectory) for a people-based one with the Slack-email adapter as the explicit fallback; the service and domain do not change. An account without an email is skipped and named (NC6).

---
<!-- COMMENTS:END -->
