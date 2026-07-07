---
id: TASK-26
title: >-
  Consolidate the Slack home: transport to infrastructure/slack/, Web client +
  classifier in integrations/slack/
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - slack
  - phase-3
  - architecture
milestone: m-3
dependencies:
  - TASK-25
references:
  - decisions/transport-slack.md
  - decisions/platform-transports.md
priority: high
ordinal: 26000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/transport-slack.md (Home) and decisions/platform-transports.md. Today the whole Slack transport (Bolt runtime in provider.py, parser.py, formatter.py, help.py, commands.py) lives in app/integrations/slack/, importing upward into infrastructure - the wrong home.

Steps:
1. Create app/infrastructure/slack/ owning: Bolt runtime + Socket Mode lifecycle, verification (from task-9), dispatch, parser, formatter, help rendering, and the SlackService reply Protocol backed by the bot-scoped Web client.
2. app/integrations/slack/ shrinks to: build_slack_web_client (authenticated AsyncWebClient factory, no lifecycle), classify_slack_error (from task-25), and settings.
3. Leave import shims at the old integrations/slack/ module paths (re-export with a deprecation comment) so app/modules/ keeps working until Phase 5; add the shims to the import-linter ignore baseline so new code cannot use them.
4. Parser tokenizer delegates to shlex.split per decisions/transport-slack.md (Parsing).
5. Slack command names and behavior unchanged - this is a code move, not a behavior change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/infrastructure/slack/ owns runtime, verification, dispatch, parser, formatter, help, SlackService; app/integrations/slack/ contains only client factory, classifier, settings (plus temporary shims)
- [ ] #2 Existing Slack commands behave identically (smoke tests or manual checklist recorded in the PR)
- [ ] #3 Shims are baseline-listed so import-linter blocks new consumers
- [ ] #4 Parser uses shlex.split; parser test suite still green
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 modules/ untouched and still functional
- [ ] #2 PR references decisions/transport-slack.md and decisions/platform-transports.md
<!-- DOD:END -->
