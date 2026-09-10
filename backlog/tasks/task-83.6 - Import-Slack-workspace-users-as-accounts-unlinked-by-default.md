---
id: TASK-83.6
title: 'Import Slack workspace users as accounts, unlinked by default'
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
dependencies:
  - TASK-83.4
references:
  - decisions/people-and-accounts.md
parent_task_id: TASK-83
priority: medium
ordinal: 173000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slack accounts must exist in the people table before SRE can link them. Accounts are keyed by (slack, team_id, user_id). Emails and display names are attributes only, so this import creates no links.

Slack user ids can change when a workspace joins an Enterprise org, so accounts keep known id aliases.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each Slack user in the configured workspace becomes one account keyed by team_id and user_id, with email and display name as attributes
- [ ] #2 The import creates no links
- [ ] #3 Re-running the import creates no duplicate accounts, including for an id recorded as an alias
- [ ] #4 The job runs behind a setting that defaults to off and makes no writes to Slack
- [ ] #5 Full test suite, ruff and mypy pass
<!-- AC:END -->
