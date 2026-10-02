---
id: TASK-26.1
title: >-
  Define the Slack handler contract in app/contracts/slack/ and move every Slack
  hookimpl onto the registrar Protocol
status: Done
assignee: []
created_date: '2026-09-24 19:58'
updated_date: '2026-10-02 15:00'
labels:
  - plugin-architecture
  - slack
milestone: m-7
dependencies:
  - TASK-25.4
  - TASK-106
  - TASK-36
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
- [x] #1 app/contracts/slack/ defines the registrar Protocol, the request and reply models and the outbound messaging Protocol, and imports no SDK runtime (slack_bolt, SocketModeHandler)
- [x] #2 Every Slack registration hookspec takes the registrar Protocol; no hookspec signature names AsyncApp, App or SlackPlatformProvider
- [x] #3 Every hookimpl under packages/ and modules/ registers through the registrar; grep finds no hookimpl receiving the Bolt app
- [x] #4 TASK-36 smoke suite green before and after; command names and behaviour unchanged
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decomposed for the single-PR size gate (about 17 production files and 500-650 LOC as one change, mixing a mechanical move with the hookspec re-sign) into three stacked layers of Stack A part 2, each its own subtask, branch and PR:
- TASK-26.1.1 (layer 7a): move the five command models to app/contracts/slack/models.py; mechanical.
- TASK-26.1.2 (layer 7b): Slack lookups in rant, incident_draft and incident_summary move behind package-owned Protocols implemented in adapters/; behaviour-neutral.
- TASK-26.1.3 (layer 7c): SlackCommandRegistrar and SlackReplyPort in app/contracts/slack/; register_slack_commands re-signed, register_slack_listeners deleted, all 8 hookimpls migrated.

Decisions: in-request replies (post to the invoking channel, ephemeral, open a view) go through SlackReplyPort, exposed as the registrar's reply property and implemented by the runtime; lookups go through each feature's own Protocol and adapters/ (decisions/platform-entrypoints.md). Reply methods return OperationResult.

AC map: #1 -> 26.1.1 (models) and 26.1.3 (Protocols); #2 and #3 -> 26.1.3; #4 and #5 -> every layer. This task is done when its three subtasks are done.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 14:59
---
ACs checked 2026-10-02 against main at f182ecd2; delivered by TASK-26.1.1 (#1517), TASK-26.1.2 (#1518) and TASK-26.1.3 (#1519), all merged. #1: app/contracts/slack/ holds models.py (CommandPayload, CommandResponse, Argument...), registrar.py (SlackCommandRegistrar) and reply.py (SlackReplySender, renamed from SlackReplyPort by TASK-136.1); rg finds no slack_bolt, socket-mode or slack_sdk import in it. #2: the only Slack registration hookspec is register_slack_commands(registrar: SlackCommandRegistrar) in contracts/plugins/hookspecs.py; register_slack_listeners(app) was deleted. #3: all 8 hookimpls (6 under packages/, modules/sre, modules/dev) take the registrar; no register_slack_* function takes app, provider or bolt. #4: tests/integration/legacy_surface 17 passed. #5: ruff clean, lint-imports 8 kept and 0 broken, full pytest run green on this tree (2858 passed), CI on #1519 all green. Status left for the human.
---
<!-- COMMENTS:END -->
