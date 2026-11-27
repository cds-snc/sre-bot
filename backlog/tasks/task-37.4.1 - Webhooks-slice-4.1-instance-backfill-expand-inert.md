---
id: TASK-37.4.1
title: 'Webhooks slice 4.1: instance backfill (expand, inert)'
status: To Do
assignee: []
created_date: '2026-11-25T20:48:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.3
references:
  - decisions/webhooks.md
  - decisions/migration.md
parent_task_id: TASK-37.4
priority: high
ordinal: 543000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The expand step of the cutover (decisions/migration.md; TASK-168 research packet section 5, row 37.4a, and Q8 step 1). A single PR from main after Stack W.

Scope: write the new optional attributes onto every existing instance in the webhooks table: instance_ref (random, non-secret), protocol, sender kinds (SNS instances get the 10 SNS kinds in today's priority order, for parity; Upptime instances the upptime kind; every other instance legacy_slack_json), the event-type and destination fields derived from hook_type, topic_arns, and owner (from the record's user_id and channel). Flag instances whose fingerprints show more than one protocol; they stay legacy until split. Runs through a GitHub Actions workflow (production changes only through workflows), with a dry run, from the TASK-46 fingerprint evidence.

Waits on: TASK-37.3, and the human evidence 1 to 6 listed in the packet (30-day webhook_invocation counts per webhook_id, matched type and path prefix; SNS topic ARNs per instance; whether any instance received the AccessRequest model; multi-type instances; user agents and source addresses; publisher per SNS kind). Record the evidence in this task's notes before implementation.

Out of scope: mounting the new route (TASK-37.4.2); any write path other than the backfill (TASK-37.6.1).

Size: ~150 production LOC plus the workflow.
Production: prod data, inert. Legacy code ignores the new attributes.
Revert / blast radius: the attributes are ignored by the legacy path; one revert of the code.
Change notice: none (inert data, packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A backfill writes instance_ref, protocol, sender kinds, event-type and destination fields, topic_arns and owner onto every instance as optional attributes; a rerun changes nothing (test)
- [ ] #2 SNS instances get the 10 SNS kinds in today's priority order, Upptime instances the upptime kind, and every other instance legacy_slack_json (test)
- [ ] #3 Instances seen with more than one protocol are flagged and stay legacy (test)
- [ ] #4 The backfill runs only through a GitHub Actions workflow with a dry-run mode; the TASK-46 evidence it uses is recorded in this task's notes (review)
- [ ] #5 The legacy route ignores the new attributes: the TASK-36.2 pins pass unchanged (test)
<!-- AC:END -->
