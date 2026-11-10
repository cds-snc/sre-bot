---
id: TASK-145.8.6
title: Cut over recreate (create resources)
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T20:12:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.8.1
  - TASK-145.7.5
  - TASK-145.7.6
  - TASK-145.8.2
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.8
priority: medium
type: feature
ordinal: 511000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L7b. `incident create resources` fills each missing reference through core and set_reference, replacing a map whole guarded on the old value; a channel with no record answers not-an-incident (the legacy record-creating branch is not carried, named in the PR body). recreate_missing_resources and _create_database_record deleted with their test.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Missing report, video call and bookmarks are recreated and referenced; a channel without a record gets the not-an-incident reply (tested; checks parent ACs #1, #5)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [ ] #3 A recreated channel moves the primary: the old primary binding is archived, the new one attached, and the record's conversation copy and channel_id move in one update guarded on record_version (attach_conversation refuses moving a primary, so this task adds the move) (tested)
- [ ] #4 The PR body states the revert target: one git revert restores the legacy surface, and the L5r rollback guard (TASK-145.8.2) keeps it reading and writing upgraded items correctly (decisions/incident-management.md Migration rule 1)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 (TASK-145.7.7): attach_conversation returns INCIDENT_RECORD_CONFLICT for a primary binding when the record names another conversation; moving the primary on recreate is this task's.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-10T20:12:00Z

---

2026-11-10 scope from TASK-145.7.5 (approved by the human): conversation creation follows incident-management.md one-channel-per-incident rules I1-I5 (TASK-145.7.5 plan 1.a4). Candidates from core/conversation_names.incident_conversation_names (legacy format, Slack-safe slug, bare name then -2..-5). I1 a record that names a conversation never creates one. I2 claim each candidate name for the incident through the IdempotencyStore (key incident:conversation_name:<tenant>:<name>); skip a name another incident claimed. I3 after any non-success create (name_taken, transient, unclassified exception or timeout) call IncidentConversation.find_own(name) first; the bots own channel bound to this incident, or unbound while this incident holds the claim, is bound and reused. I4 the same name may always be retried; the next suffix only when the channel is proven another incidents or not the bots. I5 an unknown outcome with nothing found reports the error (one warning, the pinned invoker message) without moving on; recreate retries the same name. CONVERSATION_NAME_TAKEN is an expected outcome logged at info. Plan this in full at pickup, with tests for each rule.

---
<!-- COMMENTS:END -->
