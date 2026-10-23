---
id: TASK-111.9
title: Move the Slack slice onto the files, tenant entry included
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-22T19:20:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.6.1
  - TASK-111.16
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1756
parent_task_id: TASK-111
type: feature
ordinal: 415000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slack non-secret values (timeouts, retry and error-code lists) move to [slack] and the workspace ids to [slack.tenant]; the tokens and the signing secret stay fields of the Slack slice, read as SLACK__<FIELD> (the names TASK-111.4 published: SLACK__BOT_TOKEN, SLACK__USER_TOKEN, SLACK__APP_TOKEN), because a single-workspace Bolt app is configured that way and several workspaces would use Bolt's OAuth installation store (decisions/configuration.md, 2026-10-22). A present tenant entry requires the bot token. extra=forbid. socket_mode keeps its default on the Slack slice and is not added to [slack]: TASK-112 moves it to [slack_transport] with enabled (production does not set it). SLACK_ENABLED stays until TASK-112. TASK-157 runs after this slice and adds the optional enterprise id to [slack.tenant] directly.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Slack slice reads its non-secret values, the tenant ids included, from the files and its tokens from <SLICE>__<FIELD> names
- [ ] #2 A present tenant entry missing a token still fails boot naming the key
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #4 A Slack token set without a [slack.tenant] entry fails boot naming the key (decisions/configuration.md, 2026-10-22)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-22T19:06:00Z

---

2026-10-22 (TASK-111.7 planning, human-approved): Slack tokens keep their published SLACK__<FIELD> names; no terraform or SSM rename. configuration.md no longer names Slack secrets SLACK__TENANT__<FIELD>.

---
<!-- COMMENTS:END -->
