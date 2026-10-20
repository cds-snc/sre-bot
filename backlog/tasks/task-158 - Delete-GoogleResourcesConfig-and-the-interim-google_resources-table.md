---
id: TASK-158
title: Delete GoogleResourcesConfig and the interim google_resources table
status: To Do
assignee: []
created_date: '2026-10-20 23:28'
updated_date: '2026-10-20 23:36'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-145.6
  - TASK-145.7
  - TASK-145.10
  - TASK-145.12
  - TASK-39
  - TASK-88
references:
  - decisions/configuration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1759'
type: chore
ordinal: 422000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After TASK-145.6, 145.7, 145.10, 145.12, 39 and 88 move their ids into their own feature tables, nothing reads GoogleResourcesConfig. This task deletes it, its getter and tests, and the [google_resources] table from the configuration files, and removes the item from decisions/configuration.md's tolerated list.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GoogleResourcesConfig, get_google_resources_config and their tests are deleted; rg finds no reader under app/
- [ ] #2 No configuration file has a [google_resources] table and the ownership check passes
- [ ] #3 decisions/configuration.md no longer tolerates GOOGLE_RESOURCES
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
