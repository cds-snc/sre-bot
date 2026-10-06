---
id: TASK-140.2
title: >-
  Add a Slack action and view-submission registrar so packages can handle
  buttons and modals without the Bolt app
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
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
Per the accepted interaction decision: extend the host Slack contract (contracts/slack) and SlackPlatformProvider so a package registers block-action and view-submission handlers and opens modals through the registrar, registered at startup like commands. Needed by the status-update approval modal and later by the rebuilt declare modal (TASK-38.3).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A package registers a block-action handler and a view-submission handler through a registrar Protocol in contracts/slack; no package imports slack_bolt App
- [ ] #2 Handlers are registered at startup through the plugin hooks, never at import time, and each id is registered once (duplicate ids fail boot)
- [ ] #3 Integration tests dispatch a block action and a view submission through a real Bolt app and assert ack, handler call and validation-error response
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
