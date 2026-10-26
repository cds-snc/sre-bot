---
id: TASK-111.13
title: >-
  Move the hosting slices onto the files: retry, audit, coordination, directory,
  drive, spreadsheets
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-26T19:31:00Z'
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
- [ ] #4 The provider fields of DirectorySettings, DriveSettings and SpreadsheetSettings (DIRECTORY_PROVIDER, DRIVE_PROVIDER, SPREADSHEETS_PROVIDER) are deleted, not moved: vendor choice is data, never a provider setting (decisions/workplace-systems.md, 2026-10-26), DRIVE and SPREADSHEETS allow only google, and the directory's entra_id value has no implementation (the factory raises); each factory builds the Google adapter directly; DriveSettings and SpreadsheetSettings, empty once the field goes, are deleted with their [drive] and [spreadsheets] tables, and [directory] keeps its cache, warmup and preload keys
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-26 (human approved): delete the three provider fields instead of moving them (TASK-111.10 review of the workplace capability shape; workplace-systems.md amended).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-26T15:05:00Z

---

2026-10-26: SchedulerSettings is TASK-112.4's (split from 112.3); title updated.

---
<!-- COMMENTS:END -->
