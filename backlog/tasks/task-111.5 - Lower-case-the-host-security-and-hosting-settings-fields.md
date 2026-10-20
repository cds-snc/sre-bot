---
id: TASK-111.5
title: 'Lower-case the host, security and hosting settings fields'
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
  - 'https://github.com/cds-snc/sre-bot/issues/1752'
parent_task_id: TASK-111
type: feature
ordinal: 411000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Mechanical: the fields of AppSettings, ServerSettings, LoggingSettings, SecuritySettings, SlackTransportSettings and the hosting slices (retry, audit, coordination, scheduler, directory, drive, spreadsheets) become lower snake_case with case_sensitive=False; every reader follows. Environment names do not change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Those slices declare lower snake_case fields with case_sensitive=False and read the same environment names as before
- [ ] #2 No behaviour change: the existing tests pass with only attribute renames
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
