---
id: TASK-141
title: >-
  Decide whether Slack commands move from the host command model to native Bolt
  listeners in feature entry points
status: To Do
assignee: []
created_date: '2026-10-06 19:05'
labels:
  - slack
  - architecture
dependencies:
  - TASK-140.1
references:
  - decisions/platform-entrypoints.md
  - decisions/transport-slack.md
priority: low
type: docs
ordinal: 327000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Architecture only. On 2026-10-06 (TASK-140.1) platform-entrypoints.md recorded the rule: business code is platform-neutral, a feature's platform entry point handles platform concepts with the native SDK, and the host owns registration only. Block actions and view submissions follow it from the start. Slash commands still go through the host-built command model (contracts/slack CommandPayload and CommandResponse, the argument parser, generated help, COMMAND_PREFIX handling in integrations/slack/provider.py). Decide whether commands move to native Bolt listeners, keep the model, or keep only parsing and help as shared conventions; weigh the parser and help reuse, i18n, the dev/prod prefix, TASK-33 (async Bolt) and Teams, where the Chat SDK and Teams have no slash commands.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 platform-entrypoints.md and transport-slack.md state the decision for commands with sources and a dated change line
- [ ] #2 If commands change, migration tickets are created and named in the records
<!-- AC:END -->
