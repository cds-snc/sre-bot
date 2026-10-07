---
id: TASK-142
title: >-
  Rename SlackCommandRegistrar and register_slack_commands now that they also
  register block actions and view submissions
status: To Do
assignee: []
created_date: '2026-10-06 19:53'
labels:
  - slack
dependencies:
  - TASK-140.2
references:
  - decisions/transport-slack.md
  - decisions/platform-entrypoints.md
priority: low
ordinal: 328000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After TASK-140.2 the registrar Protocol and its hookspec register commands, block actions and view submissions, so the command-only names mislead. Mechanical rename only (e.g. SlackRegistrar / register_slack_handlers, names decided in this task per the Protocol naming rule from TASK-136.1) across contracts/slack, contracts/plugins/hookspecs.py, server/plugins, integrations/slack/provider.py, every package hookimpl, test fakes and the decision records that name them; no behavior change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 SlackCommandRegistrar and register_slack_commands are renamed everywhere in app/, tests and decisions/; no old name remains (rg)
- [ ] #2 No behavior change: the legacy-surface Slack registration tests pass unchanged apart from names
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
