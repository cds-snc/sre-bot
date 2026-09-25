---
id: TASK-83.15
title: >-
  Let a privileged user trigger the people import on demand, and record
  per-change import as the upgrade path
status: To Do
assignee: []
created_date: '2026-09-25 19:59'
labels:
  - identity
milestone: m-4
dependencies:
  - TASK-83.5
  - TASK-131
references:
  - decisions/people-and-accounts.md
  - decisions/authorization.md
parent_task_id: TASK-83
priority: low
ordinal: 282000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human direction 2026-09-25: the hourly people import (TASK-83.5) can also be run on demand by a privileged user, for example right after an onboarding.

The trigger is a feature permission declared through the authorization policy (TASK-131), for example people.import.run, at role level and privileged, so the IdP is always re-checked before it runs. It runs the same job body as the schedule, under the same lease, so a manual run and a scheduled run never overlap. The result (counts only) is returned to the caller, and the run is audited.

Per-change import is recorded, not built: the Directory API users.watch push channel (events add, delete, update, makeAdmin, undelete) would import one user when they change. decisions/authorization.md defers push notifications, because Google documents them as not fully reliable and they need a public webhook and channel renewal, so hourly polling stays authoritative.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A caller holding the privileged import permission can start the import; anyone else is refused, and every start is audited with the caller's person id
- [ ] #2 A manual run uses the scheduled job's body and lease; a run already in progress is reported instead of starting a second one
- [ ] #3 The caller gets counts only (created, updated, deactivated), never personal data
- [ ] #4 The task records Directory users.watch as the per-change upgrade path, with its reliability caveat, and builds no push channel
- [ ] #5 Full test suite, ruff and mypy pass
<!-- AC:END -->
