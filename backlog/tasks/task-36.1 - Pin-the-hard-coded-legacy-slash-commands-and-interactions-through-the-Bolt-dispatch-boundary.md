---
id: TASK-36.1
title: >-
  Pin the hard-coded legacy slash commands and interactions through the Bolt
  dispatch boundary
status: To Do
assignee: []
created_date: '2026-09-28 14:36'
labels:
  - migration
  - testing
milestone: m-5
dependencies:
  - TASK-36
references:
  - decisions/testing.md
  - decisions/migration.md
  - decisions/transport-slack.md
parent_task_id: TASK-36
priority: high
ordinal: 285000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-36 pins only the 8 register_slack_commands hookimpls TASK-26.1 rewrites. The legacy surface registered through the hard-coded _register_legacy_handlers() list in app/server/lifespan.py is not yet pinned: 7 slash commands (sre, aws, talent-role, secret, atip/aiprp, incident) and 31 interactions (17 actions, 10 views, 4 events).

Add pinning tests for those rows of the TASK-36 inventory in app/tests/integration/legacy_surface/, reusing the TASK-36 harness: build a real slack_bolt App, register through the real startup path, drive it with App.dispatch(BoltRequest) and assert on ack, response and faked side effects only. These tests gate TASK-26.2 (runtime move) and the TASK-38, TASK-39 and TASK-88 surface rebuilds. Split by module group if the size gate requires it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every hard-coded legacy slash command and interaction row in the TASK-36 inventory has a pinning test driven through App.dispatch, or an explicit not-pinned reason with its owning ticket
- [ ] #2 Tests live in app/tests/integration/legacy_surface/, use fakes only and run in the normal pytest tests --ignore=tests/smoke gate
- [ ] #3 The TASK-36 inventory marks each row pinned by this task
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
