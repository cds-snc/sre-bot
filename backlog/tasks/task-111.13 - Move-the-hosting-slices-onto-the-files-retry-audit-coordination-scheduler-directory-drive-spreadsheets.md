---
id: TASK-111.13
title: >-
  Move the hosting slices onto the files: retry, audit, coordination, scheduler,
  directory, drive, spreadsheets
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-23T19:22:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.5.1
  - TASK-111.16
  - TASK-111.17
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1746
parent_task_id: TASK-111
type: feature
ordinal: 419000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The hosting slices (RetrySettings, AuditSettings, ConditionalWriteSettings, DirectorySettings, DriveSettings, SpreadsheetSettings) move onto the files: each becomes a ConfigurationSlice with its own table and <TABLE>__ prefix, declares no per-field alias, sets extra=forbid, and has its defaults written in base.toml. Production sets none of their names (doc-14), so no production value moves. RetrySettings moves from infrastructure/configuration/infrastructure/retry.py to its owner, infrastructure/resilience/retry/, and InfrastructureSettings (infrastructure/configuration/base.py) is deleted once no slice inherits it. TASK-119, TASK-120 and TASK-121 later move the drive, directory and spreadsheets classes without touching the files. SchedulerSettings moved to TASK-112.3 on 2026-10-23 (its [scheduler] table gains the enabled run switch there).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each hosting slice reads its table from the files with extra=forbid and its defaults in base.toml, and no longer reads its old flat environment names
- [ ] #2 RetrySettings lives in infrastructure/resilience/retry/ and InfrastructureSettings is deleted
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
