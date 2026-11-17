---
id: TASK-165.11
title: Rebind an incident's primary conversation to a new channel
status: To Do
assignee: []
created_date: '2026-11-17T15:29:00Z'
updated_date: '2026-11-17T15:47:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.13
parent_task_id: TASK-165
priority: low
ordinal: 527000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Moves an incident's primary conversation to a new channel when the old one is lost or replaced. TASK-145.7 scenario 3 deferred this out of Stack L (recreate runs inside the channel and never moves the conversation); TASK-145.8.6 AC #3 (added 2026-11-10) moved here 2026-11-17 (human). Slack bot tokens cannot unarchive a conversation, so an archived primary is otherwise repaired only by a human unarchive. Plan in full at pickup: confirm a real use case first (no Runbook or Handbook step names it today) and judge it against decisions/incident-management.md (Bindings, One conversation per incident I1-I5) and incident-coordination.md once written.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Rebinding archives the old primary binding (archived_at), attaches the new conversation as primary, and moves the record's conversation copy in one update guarded on record_version; attach_conversation keeps refusing a primary move (tested)
- [ ] #2 A new channel is created through the shared I1-I5 conversation loop (TASK-145.7.9, response/service/conversation.py), never a second copy of it (tested)
- [ ] #3 Runs after TASK-145.13 retires channel_id and by_channel, so the move writes one conversation copy
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-17: TASK-145.8.6 retired /sre incident create; the attach_conversation primary-move refusal (test docstring in test_incident_core_incident_store_attach_conversation.py) cites this task.
<!-- SECTION:NOTES:END -->
