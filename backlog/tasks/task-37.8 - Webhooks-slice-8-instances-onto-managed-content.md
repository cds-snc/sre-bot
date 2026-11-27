---
id: TASK-37.8
title: 'Webhooks slice 8: instances onto managed content'
status: To Do
assignee: []
created_date: '2026-11-25T20:49:00Z'
updated_date: '2026-11-27T16:47:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.6.1
  - TASK-197.2
references:
  - decisions/managed-content.md
  - decisions/webhooks.md
parent_task_id: TASK-37
priority: medium
ordinal: 550000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Moves webhook instances onto managed content (TASK-168 research packet section 5, row 37.8, and Q10, OQ5; decisions/managed-content.md). Off the TASK-40 path.

Scope: on the version store built by the first managed content kind, give webhook instances versions, export (secrets excluded; an import mints new secrets) and a per-kind kill switch, and end managed-content.md's interim tolerance for instances written by conditional update plus audit (managed-content.md:106).

Waits on: TASK-37.6.1, and the first of TASK-166, TASK-165 or the TASK-146 re-cut to build the managed-content version store. That dependency is added with the CLI when one of them lands (see the notes).

Out of scope: the WebhookAdmin API surface itself (TASK-37.6.1).

Size: ~300 production LOC.
Production: prod.
Revert / blast radius: one revert returns instances to conditional updates plus audit.
Change notice: none expected unless the admin flow changes visibly; confirm at planning.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every instance write through WebhookAdmin records a version on the managed-content version store (test)
- [ ] #2 Export never includes a secret, and an import mints new secrets (test)
- [ ] #3 A per-kind kill switch disables webhook instances without a deploy (test)
- [ ] #4 decisions/managed-content.md no longer carries the interim tolerance for webhook instances (review)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dependency to add when it lands: the first of TASK-166, TASK-165 or the TASK-146 re-cut that builds the managed-content version store (TASK-168 packet section 7.2). Add it with backlog task edit 37.8 --dep TASK-37.6.1,<that task> once known.

2026-11-27 (TASK-37.2.2 planning, human-approved Q3a): a non-public value in a managed record is sealed through the platform field-encryption contract (TASK-197.2) with the record's identity as context, per organisation-content.md.
<!-- SECTION:NOTES:END -->
