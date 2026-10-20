---
id: TASK-111.2
title: >-
  Load settings from base and per-environment TOML files through a contracts
  settings base and a host loader
status: To Do
assignee: []
created_date: '2026-10-20 23:25'
updated_date: '2026-10-20 23:36'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.1
references:
  - decisions/configuration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1749'
parent_task_id: TASK-111
type: feature
ordinal: 408000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
pydantic-settings >= 2.15 (toml_table_header). contracts/configuration.py holds the settings-slice base (each slice names its table) and the Protocol that supplies the file list; server/configuration/ implements it: file selection from ENVIRONMENT, base then <environment>.toml, deep merge, existence check, registered in lifespan's configuration phase before any slice builds. app/config/{base,local,ci,production}.toml ship in the image. LoggingSettings is the first slice on it and gains log_level from AppSettings.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 pydantic-settings is pinned to a release >= 2.15 and the lock file is updated
- [ ] #2 A slice built on the contracts base reads its own table from base.toml deep-merged with <ENVIRONMENT>.toml; an environment variable overrides a file value and a file value overrides the code default
- [ ] #3 A missing base or environment file, malformed TOML, a non-table value or an unknown key in a slice's table fails boot with a message naming the file, table and key
- [ ] #4 app/config holds base.toml and one file per ENVIRONMENT value; a test fails when an ENVIRONMENT value has no file or a file does not parse
- [ ] #5 LoggingSettings reads [logging] (log_level, redaction_extra_keys) from the files; production log output is unchanged
- [ ] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
