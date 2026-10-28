---
id: TASK-111.13
title: >-
  Move the hosting slices onto the files: retry, audit, coordination, directory,
  drive, spreadsheets
status: Done
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-28T19:48:00Z'
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
- [x] #1 Each remaining hosting slice (directory, audit, coordination) reads its table from the files with extra=forbid and its defaults in base.toml, no longer reads its old flat environment names, and its unread fields are deleted (TASK-111.13.1, 111.13.3)
- [x] #2 RetrySettings is deleted with the unused infrastructure/resilience package (TASK-111.13.2), and InfrastructureSettings and the infrastructure/configuration/infrastructure package are deleted (TASK-111.13.3)
- [x] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #4 The provider fields of DirectorySettings, DriveSettings and SpreadsheetSettings (DIRECTORY_PROVIDER, DRIVE_PROVIDER, SPREADSHEET_PROVIDER) are deleted, not moved (decisions/workplace-systems.md, 2026-10-26); each factory builds the Google adapter directly and the adapters take no settings argument; DriveSettings and SpreadsheetSettings are deleted with their [drive] and [spreadsheets] tables, and [directory] holds only require_startup_warmup until TASK-128 deletes it (TASK-111.13.1)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Coordinator since 2026-10-28 (human approved the split). The original single-PR plan (planned against main 83f895ab) tripped the size gate (~27 production files; behaviour change mixed with a mechanical move) and the program-scope review found infrastructure/resilience/ unused in production. Work is in three subtasks, one PR each: TASK-111.13.1 directory, drive, spreadsheets; TASK-111.13.2 delete infrastructure/resilience/ and RetrySettings (supersedes TASK-59); TASK-111.13.3 audit and coordination onto the files, InfrastructureSettings deleted (waits on .1 and .2). Rulings 2026-10-28 (human): dead code deleted; a key does not repeat its table; backing-resource names are deployment configuration (decisions/configuration.md). The ACs here are checked as the subtasks verify them.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-26 (human approved): delete the three provider fields instead of moving them (TASK-111.10 review of the workplace capability shape; workplace-systems.md amended).

2026-10-28: split into 111.13.1 to 111.13.3 (human); ACs reworded to the split and the dead-code rulings.

- 2026-10-28: all ACs checked from the subtasks: 111.13.1 (#1801), 111.13.2 (#1802) and 111.13.3 (#1803) merged and in production on sre-bot-task:64 (the 111.14 deploy; post features PASS 19:17Z, app working, human). Done (human).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-26T15:05:00Z

---

2026-10-26: SchedulerSettings is TASK-112.4's (split from 112.3); title updated.

---
<!-- COMMENTS:END -->
