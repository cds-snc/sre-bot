---
id: TASK-83.10
title: Cut retro attendee resolution over to people with an explicit fallback
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
dependencies:
  - TASK-83.9
references:
  - app/modules/incident/schedule_retro.py
parent_task_id: TASK-83
priority: medium
ordinal: 177000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
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
