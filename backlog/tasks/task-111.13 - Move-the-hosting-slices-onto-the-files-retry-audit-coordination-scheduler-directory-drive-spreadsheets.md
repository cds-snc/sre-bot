---
id: TASK-111.13
title: >-
  Move the hosting slices onto the files: retry, audit, coordination, scheduler,
  directory, drive, spreadsheets
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-22T13:57:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.5.1
  - TASK-111.16
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1746
parent_task_id: TASK-111
type: feature
ordinal: 419000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The hosting slices declare their tables, take <SLICE>__ prefixes and extra=forbid; their defaults are written in base.toml. TASK-119, TASK-120 and TASK-121 later move the drive, directory and spreadsheets classes without touching the files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each hosting slice reads its table from the files with extra=forbid and its defaults in base.toml
- [ ] #2 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
