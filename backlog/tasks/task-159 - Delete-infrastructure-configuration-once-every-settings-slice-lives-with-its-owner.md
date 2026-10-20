---
id: TASK-159
title: >-
  Delete infrastructure/configuration/ once every settings slice lives with its
  owner
status: To Do
assignee: []
created_date: '2026-10-20 23:28'
updated_date: '2026-10-20 23:36'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111
  - TASK-145.13
  - TASK-40
  - TASK-88
references:
  - decisions/configuration.md
  - decisions/plugin-architecture.md
  - 'https://github.com/cds-snc/sre-bot/issues/1760'
type: chore
ordinal: 423000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-111 empties infrastructure/configuration/ except features/incident.py, features/sre_ops.py and features/aws_ops.py (base.py replaced by the contracts settings base, app.py by the server/configuration identity slice, ServerSettings to server/, retry to its hosting owner; atip and groups deleted in TASK-111.14). Those three move with their features: incident with TASK-145.13, sre_ops with TASK-40, aws_ops with TASK-88. This task deletes the empty package and the tolerated-list item in decisions/configuration.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/infrastructure/configuration/ no longer exists and nothing imports it
- [ ] #2 decisions/configuration.md no longer tolerates feature slices in infrastructure/configuration/features/
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
