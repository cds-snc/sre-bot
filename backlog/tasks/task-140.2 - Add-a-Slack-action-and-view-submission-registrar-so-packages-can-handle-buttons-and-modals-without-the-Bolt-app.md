---
id: TASK-140.2
title: >-
  Add a Slack action and view-submission registrar so packages can handle
  buttons and modals without the Bolt app
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-06 19:08'
labels:
  - incident
dependencies:
  - TASK-140.1
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 321000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per decisions/transport-slack.md (Block actions and view submissions) and platform-entrypoints.md rules 2-3: extend the registrar Protocol in contracts/slack and SlackPlatformProvider so a package's entrypoints/slack.py registers native Bolt listeners for block actions and view submissions by exact action_id or callback_id, at startup like commands. Listeners receive Bolt's own arguments (ack, body, client, respond) and open modals with Bolt's client; the host never normalizes the payload and never hands out the App. Ids carry the plugin's entry-point name. Options, shortcuts, view_closed, regex ids and middleware are out of scope until a feature needs them. Needed by the status-update approval modal and later by the rebuilt declare modal (TASK-38.3).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A package registers a block-action handler and a view-submission handler through a registrar Protocol in contracts/slack; no package imports slack_bolt App
- [ ] #2 Handlers are registered at startup through the plugin hooks, never at import time, and each id is registered once (duplicate ids fail boot)
- [ ] #3 Integration tests dispatch a block action and a view submission through a real Bolt app and assert ack, handler call and validation-error response
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #5 import-linter allows slack_bolt in packages only from entrypoints/slack.py modules (transport-slack.md Checks)
<!-- AC:END -->
