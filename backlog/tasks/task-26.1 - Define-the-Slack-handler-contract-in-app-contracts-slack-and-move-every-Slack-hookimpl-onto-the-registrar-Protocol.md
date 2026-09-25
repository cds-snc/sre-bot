---
id: TASK-26.1
title: >-
  Define the Slack handler contract in app/contracts/slack/ and move every Slack
  hookimpl onto the registrar Protocol
status: To Do
assignee: []
created_date: '2026-09-24 19:58'
labels:
  - plugin-architecture
  - slack
milestone: m-7
dependencies:
  - TASK-106
  - TASK-25.4
references:
  - decisions/platform-entrypoints.md
  - decisions/transport-slack.md
  - decisions/interaction-toolkits.md
parent_task_id: TASK-26
priority: high
type: task
ordinal: 247000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-26. decisions/platform-entrypoints.md rule 2: features never receive SDK runtime objects. Registration hookspecs take the platform's registrar Protocol from the handler contract, never the Bolt AsyncApp or SlackPlatformProvider.

Today the hookspecs are register_slack_commands(provider: SlackPlatformProvider) and register_slack_listeners(app: AsyncApp) in app/infrastructure/plugins/specs.py. They hand features runtime objects, and they prevent the hookspecs from moving to app/contracts/ (contracts may not import the runtime). This slice defines, in app/contracts/slack/:
- the registrar Protocol;
- typed inbound request and reply models (pure data; slack_sdk model types allowed);
- the outbound messaging Protocol handlers use to reply.
It then re-signs the Slack registration hookspecs against the registrar, where they live today, and migrates every hookimpl in packages/ and modules/ in the same change. The runtime implements the registrar where it lives today; it moves in slice 2.

This is also the replacement that TASK-67 names when it retires register_slack_commands.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/contracts/slack/ defines the registrar Protocol, the request and reply models and the outbound messaging Protocol, and imports no SDK runtime (slack_bolt, SocketModeHandler)
- [ ] #2 Every Slack registration hookspec takes the registrar Protocol; no hookspec signature names AsyncApp, App or SlackPlatformProvider
- [ ] #3 Every hookimpl under packages/ and modules/ registers through the registrar; grep finds no hookimpl receiving the Bolt app
- [ ] #4 TASK-36 smoke suite green before and after; command names and behaviour unchanged
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
