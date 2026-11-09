---
id: TASK-145.7.6
title: >-
  VideoCall in core: features/incident/meet moves to
  core/adapters/google_meet.py
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
dependencies: []
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 503000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L4b (approved program in TASK-145.7's plan, section 2; outline in the parent plan). Mechanical move plus a VideoCall Protocol (create -> OperationResult[VideoCallReference]) and fake; no subject kwarg (TASK-145.6 AC #7); modules/incident/core.py:12 repointed; features/incident/meet/ deleted.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/incident/meet does not exist; core/adapters/google_meet.py and the VideoCall Protocol and fake exist with tests; the legacy import is repointed (checks parent AC #3)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
