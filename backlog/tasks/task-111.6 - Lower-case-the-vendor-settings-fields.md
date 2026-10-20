---
id: TASK-111.6
title: Lower-case the vendor settings fields
status: To Do
assignee: []
created_date: '2026-10-20 23:25'
updated_date: '2026-10-20 23:36'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.2
references:
  - decisions/configuration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1753'
parent_task_id: TASK-111
type: feature
ordinal: 412000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Mechanical: the fields of the integrations/<vendor>/settings.py slices (slack, google_workspace, aws, openai, notify, trello, opsgenie, maxmind, sentinel) become lower snake_case with case_sensitive=False; every reader follows. Environment names do not change. Split in two by vendor group if it exceeds the size gate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The vendor slices declare lower snake_case fields with case_sensitive=False and read the same environment names as before
- [ ] #2 No behaviour change: the existing tests pass with only attribute renames
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
