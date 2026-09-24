---
id: TASK-83.6
title: 'Import Slack workspace users as accounts, unlinked by default'
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-09-24 20:08'
labels:
  - identity
dependencies:
  - TASK-83.4
  - TASK-25.4
  - TASK-64
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

Updated 2026-09-24: Slack users are read through an adapter in app/capabilities/people/adapters/ built on the Slack client factory (TASK-25.4), classified with classify_slack_error. The job registers through the register_background_jobs hookspec as a Tier-2 job with a lease from the coordination contract.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each Slack user in the configured workspace becomes one account keyed by team_id and user_id, with email and display name as attributes
- [ ] #2 The import creates no links
- [ ] #3 Re-running the import creates no duplicate accounts, including for an id recorded as an alias
- [ ] #4 The job runs behind a setting that defaults to off and makes no writes to Slack
- [ ] #5 Full test suite, ruff and mypy pass
- [ ] #6 Slack is read only through app/capabilities/people/adapters/ using the Slack client factory; the job registers through register_background_jobs as a Tier-2 job with a lease
<!-- AC:END -->
