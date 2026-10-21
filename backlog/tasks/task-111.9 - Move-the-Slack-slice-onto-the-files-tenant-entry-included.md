---
id: TASK-111.9
title: Move the Slack slice onto the files, tenant entry included
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-21T21:08:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.6.1
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1756
parent_task_id: TASK-111
type: feature
ordinal: 415000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slack non-secret values (socket_mode, timeouts, retry and error-code lists, the tenant team id) move to [slack] and [slack.tenant]; tokens are read as SLACK__<FIELD> or SLACK__TENANT__<FIELD>; extra=forbid. SLACK_ENABLED stays until TASK-112. TASK-157 runs after this slice and adds the optional enterprise id to [slack.tenant] directly.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Slack slice reads its non-secret values, the tenant ids included, from the files and its tokens from <SLICE>__<FIELD> names
- [ ] #2 A present tenant entry missing a token still fails boot naming the key
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
